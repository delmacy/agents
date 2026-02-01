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

    def worker_llm(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        return LLM(
            model=os.getenv("MODEL", "deepseek/deepseek-reasoner"),
            base_url="https://api.deepseek.com",
            api_key=api_key,
            temperature=0.2
        )

    def chat_llm(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        return LLM(
            model=os.getenv("MANAGER_MODEL", "deepseek-chat"),
            base_url="https://api.deepseek.com",
            api_key=api_key,
            temperature=0.7
        )

    # --- AGENTS ---

    @agent
    def product_manager_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['product_manager_agent'],
            tools=[self.file_writer, self.file_reader],
            verbose=True,
            llm=self.chat_llm(),
            allow_delegation=False
        )

    @agent
    def architect_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['architect_agent'],
            tools=[self.file_writer, self.file_reader],
            verbose=True,
            llm=self.worker_llm(),
            allow_delegation=False
        )

    @agent
    def tech_lead_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['tech_lead_agent'],
            tools=[self.file_writer, self.file_reader],
            verbose=True,
            llm=self.worker_llm(),
            allow_delegation=False
        )

    @agent
    def backend_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['backend_agent'],
            tools=[self.file_writer, self.file_reader],
            verbose=True,
            llm=self.worker_llm(),
            allow_delegation=False
        )

    @agent
    def review_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['review_agent'],
            tools=[self.file_writer, self.file_reader, self.dir_reader],
            verbose=True,
            llm=self.worker_llm(),
            allow_delegation=False
        )

    @agent
    def devops_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['devops_agent'],
            tools=[self.file_writer, self.file_reader, self.dir_reader, self.venv_tool],
            verbose=True,
            llm=self.worker_llm(),
            allow_delegation=False
        )

    @agent
    def qa_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['qa_agent'],
            tools=[self.file_writer, self.file_reader, self.dir_reader, self.venv_tool],
            verbose=True,
            llm=self.worker_llm(),
            allow_delegation=False
        )

    # --- TASKS ---

    @task
    def discovery_task(self) -> Task:
        return Task(
            config=self.tasks_config['discovery_task'],
            agent=self.product_manager_agent(),
            callback=self.task_callback
        )

    @task
    def blueprint_task(self) -> Task:
        return Task(
            config=self.tasks_config['blueprint_task'],
            agent=self.architect_agent(), # Architect leads, Tech Lead supports via internal collaboration or separate task?
            # Prompt implies "leadership_crew (Architect + Tech Lead)".
            # We can put both agents in the crew. The task is assigned to Architect.
            # Ideally Tech Lead reviews it. Let's create a review subtask or assume collaboration if in same crew.
            # But here we assign to Architect.
            callback=self.task_callback
        )

    @task
    def coding_task(self) -> Task:
        return Task(
            config=self.tasks_config['coding_task'],
            agent=self.backend_agent(),
            callback=self.task_callback
        )

    @task
    def validation_task(self) -> Task:
        return Task(
            config=self.tasks_config['validation_task'],
            agent=self.review_agent(),
            context=[self.coding_task()],
            callback=self.task_callback
        )

    @task
    def infrastructure_task(self) -> Task:
        return Task(
            config=self.tasks_config['infrastructure_task'],
            agent=self.devops_agent(),
            context=[self.coding_task()],
            callback=self.task_callback
        )

    @task
    def testing_task(self) -> Task:
        return Task(
            config=self.tasks_config['testing_task'],
            agent=self.qa_agent(),
            context=[self.coding_task()],
            callback=self.task_callback
        )

    def task_callback(self, task_output):
        """Callback to log task completion."""
        try:
            result_summary = str(task_output)[:200]
            self.state_manager.log_task(
                job_id=self.job_id,
                task_name="Unknown Task (Callback)",
                status="SUCCESS",
                details=result_summary
            )
        except Exception as e:
            print(f"Error logging task: {e}")

    # --- CREWS ---

    @crew
    def discovery_crew(self) -> Crew:
        return Crew(
            agents=[self.product_manager_agent()],
            tasks=[self.discovery_task()],
            process=Process.sequential,
            verbose=True
        )

    @crew
    def leadership_crew(self) -> Crew:
        # Architect and Tech Lead
        # Task is blueprint_task (assigned to Architect).
        # To involve Tech Lead, we might need a separate task or just have them in the crew for potential delegation if allowed.
        # Simple approach: Architect does the work.
        return Crew(
            agents=[self.architect_agent(), self.tech_lead_agent()],
            tasks=[self.blueprint_task()],
            process=Process.sequential,
            verbose=True
        )

    @crew
    def development_crew(self) -> Crew:
        # Backend + Review (Validation Gate)
        return Crew(
            agents=[self.backend_agent(), self.review_agent()],
            tasks=[self.coding_task(), self.validation_task()],
            process=Process.sequential,
            verbose=True
        )

    @crew
    def execution_crew(self) -> Crew:
        # Build (DevOps) + QA (Sandbox)
        return Crew(
            agents=[self.devops_agent(), self.qa_agent()],
            tasks=[self.infrastructure_task(), self.testing_task()],
            process=Process.sequential,
            verbose=True
        )
