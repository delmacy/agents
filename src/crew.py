import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import FileWriterTool, FileReadTool, DirectoryReadTool
from src.state_manager import StateManager
from src.tools.venv_execution_tool import VenvExecutionTool

@CrewBase
class EmpresaSoftwareCrew:
    """EmpresaSoftwareCrew crew"""
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.output_dir = f"output/{self.job_id}"
        self.state_manager = StateManager()

        # Tools
        self.file_writer = FileWriterTool(directory=self.output_dir)
        self.file_reader = FileReadTool(directory=self.output_dir)
        self.dir_reader = DirectoryReadTool(directory=self.output_dir)
        self.venv_tool = VenvExecutionTool(job_id=self.job_id)

    def step_callback(self, agent_output, **kwargs):
        """Callback to log every thought/step of the agents.
        Agora também persiste o pensamento no histórico de chat para que o frontend consiga exibir debates em tempo real."""
        try:
            step_details = str(agent_output)
            clean_details = step_details[:800] + "..." if len(step_details) > 800 else step_details

            # Log tradicional
            self.state_manager.log_task(
                job_id=self.job_id,
                task_name="Agent Thinking...", 
                status="EXECUTING",
                details=clean_details
            )

            # Tenta inferir o nome do agente dos kwargs para gravar no chat
            agent_name = kwargs.get('agent_name')
            agent_obj = kwargs.get('agent')
            if not agent_name and agent_obj:
                try:
                    if hasattr(agent_obj, 'config') and isinstance(agent_obj.config, dict):
                        agent_name = agent_obj.config.get('name') or str(agent_obj)
                    else:
                        agent_name = str(agent_obj)
                except Exception:
                    agent_name = str(agent_obj)

            if not agent_name:
                agent_name = "agent"

            # Salva no histórico de chat para o frontend
            try:
                self.state_manager.add_chat_message(self.job_id, sender=agent_name, role="agent", message=clean_details)
            except Exception:
                # Evita que falhas aqui quebrem o fluxo principal
                pass

        except Exception:
            pass

    def worker_llm(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is missing via os.getenv")

        # TRUQUE: O CrewAI precisa ver "OPENAI_API_KEY" definida, mesmo que não use.
        # Definimos ela como sendo a mesma do DeepSeek para passar na validação.
        os.environ["OPENAI_API_KEY"] = api_key

        return LLM(
            # Usamos o prefixo 'openai/' para usar o cliente genérico compatível
            model="openai/" + os.getenv("MODEL", "deepseek-reasoner"),
            base_url="https://api.deepseek.com",
            api_key=api_key,
            temperature=0.1
        )

    def chat_llm(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is missing via os.getenv")

        os.environ["OPENAI_API_KEY"] = api_key

        return LLM(
            model="openai/" + os.getenv("MANAGER_MODEL", "deepseek-chat"),
            base_url="https://api.deepseek.com",
            api_key=api_key,
            temperature=0.7
        )
    # --- AGENTS ---
    @agent
    def product_manager_agent(self) -> Agent:
        return Agent(config=self.agents_config['product_manager_agent'], tools=[self.file_writer, self.file_reader], verbose=True, llm=self.chat_llm(), step_callback=self.step_callback)

    @agent
    def architect_agent(self) -> Agent:
        return Agent(config=self.agents_config['architect_agent'], tools=[self.file_writer, self.file_reader], verbose=True, llm=self.worker_llm(), step_callback=self.step_callback)

    @agent
    def technical_designer_agent(self) -> Agent:
        return Agent(config=self.agents_config['technical_designer_agent'], tools=[self.file_writer, self.file_reader, self.dir_reader], verbose=True, llm=self.worker_llm(), step_callback=self.step_callback)

    @agent
    def scrum_master_agent(self) -> Agent:
        return Agent(config=self.agents_config['scrum_master_agent'], tools=[self.file_writer, self.file_reader], verbose=True, llm=self.worker_llm(), step_callback=self.step_callback)

    @agent
    def backend_agent(self) -> Agent:
        return Agent(config=self.agents_config['backend_agent'], tools=[self.file_writer, self.file_reader], verbose=True, llm=self.worker_llm(), step_callback=self.step_callback)

    @agent
    def devops_agent(self) -> Agent:
        return Agent(config=self.agents_config['devops_agent'], tools=[self.file_writer, self.file_reader, self.venv_tool], verbose=True, llm=self.worker_llm(), step_callback=self.step_callback)

    @agent
    def qa_strategist_agent(self) -> Agent:
        return Agent(config=self.agents_config['qa_strategist_agent'], tools=[self.file_writer, self.file_reader, self.dir_reader], verbose=True, llm=self.worker_llm(), step_callback=self.step_callback)

    @agent
    def qa_automation_agent(self) -> Agent:
        return Agent(config=self.agents_config['qa_automation_agent'], tools=[self.file_writer, self.file_reader, self.venv_tool], verbose=True, llm=self.worker_llm(), step_callback=self.step_callback)

    # --- TASKS ---
    @task
    def discovery_task(self) -> Task:
        return Task(config=self.tasks_config['discovery_task'], agent=self.product_manager_agent())

    @task
    def architecture_task(self) -> Task:
        return Task(config=self.tasks_config['architecture_task'], agent=self.architect_agent())

    @task
    def logic_specification_task(self) -> Task:
        return Task(config=self.tasks_config['logic_specification_task'], agent=self.technical_designer_agent(), context=[self.architecture_task()])

    @task
    def sprint_planning_task(self) -> Task:
        return Task(config=self.tasks_config['sprint_planning_task'], agent=self.scrum_master_agent(), context=[self.logic_specification_task(), self.architecture_task()])

    @task
    def coding_task(self) -> Task:
        return Task(config=self.tasks_config['coding_task'], agent=self.backend_agent(), context=[self.sprint_planning_task(), self.logic_specification_task()])

    @task
    def environment_setup_task(self) -> Task:
        return Task(config=self.tasks_config['environment_setup_task'], agent=self.devops_agent(), context=[self.coding_task()])

    @task
    def test_planning_task(self) -> Task:
        return Task(config=self.tasks_config['test_planning_task'], agent=self.qa_strategist_agent(), context=[self.logic_specification_task()])

    @task
    def test_implementation_task(self) -> Task:
        return Task(config=self.tasks_config['test_implementation_task'], agent=self.qa_automation_agent(), context=[self.test_planning_task(), self.coding_task()])

    # --- CREWS (Split for Control Loop) ---
    
    @crew
    def planning_crew(self) -> Crew:
        # Phase 1 & 2: Define Logic
        return Crew(
            agents=[self.product_manager_agent(), self.architect_agent(), self.technical_designer_agent(), self.scrum_master_agent()],
            tasks=[self.discovery_task(), self.architecture_task(), self.logic_specification_task(), self.sprint_planning_task()],
            process=Process.sequential, verbose=True
        )

    @crew
    def coding_crew(self) -> Crew:
        # Phase 3: Build & Install
        return Crew(
            agents=[self.backend_agent(), self.devops_agent()],
            tasks=[self.coding_task(), self.environment_setup_task()],
            process=Process.sequential, verbose=True
        )

    @crew
    def qa_crew(self) -> Crew:
        # Phase 4: Verify
        return Crew(
            agents=[self.qa_strategist_agent(), self.qa_automation_agent()],
            tasks=[self.test_planning_task(), self.test_implementation_task()],
            process=Process.sequential, verbose=True
        )