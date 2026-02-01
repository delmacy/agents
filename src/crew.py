import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import FileWriterTool, FileReadTool, DirectoryReadTool
from src.state_manager import StateManager

@CrewBase
class EmpresaSoftwareCrew:
    """EmpresaSoftwareCrew crew"""
    agents_config = 'src/config/agents.yaml'
    tasks_config = 'src/config/tasks.yaml'

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.output_dir = f"output/{self.job_id}"
        self.worker_llm = self.configurar_worker_llm()
        self.state_manager = StateManager()

    def configurar_worker_llm(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set in environment variables.")

        return LLM(
            model=os.getenv("MODEL", "deepseek/deepseek-reasoner"),
            base_url="https://api.deepseek.com",
            api_key=api_key,
            temperature=0.2
        )

    @agent
    def backend_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['backend_agent'],
            tools=[FileWriterTool(directory=self.output_dir)],
            verbose=True,
            llm=self.worker_llm,
            allow_delegation=False
        )

    @agent
    def review_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['review_agent'],
            tools=[
                FileWriterTool(directory=self.output_dir),
                FileReadTool(directory=self.output_dir),
                DirectoryReadTool(directory=self.output_dir)
            ],
            verbose=True,
            llm=self.worker_llm,
            allow_delegation=False
        )

    @agent
    def devops_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['devops_agent'],
            tools=[
                FileWriterTool(directory=self.output_dir),
                FileReadTool(directory=self.output_dir),
                DirectoryReadTool(directory=self.output_dir)
            ],
            verbose=True,
            llm=self.worker_llm,
            allow_delegation=False
        )

    @agent
    def qa_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['qa_agent'],
            tools=[
                FileWriterTool(directory=self.output_dir),
                FileReadTool(directory=self.output_dir),
                DirectoryReadTool(directory=self.output_dir)
            ],
            verbose=True,
            llm=self.worker_llm,
            allow_delegation=False
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
        """Callback to log task completion to SQLite."""
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

    @crew
    def initial_crew(self) -> Crew:
        """Crew for coding and validation"""
        return Crew(
            agents=[self.backend_agent(), self.review_agent()],
            tasks=[self.coding_task(), self.validation_task()],
            process=Process.sequential,
            verbose=True
        )

    @crew
    def final_crew(self) -> Crew:
        """Crew for infrastructure and testing"""
        return Crew(
            agents=[self.devops_agent(), self.qa_agent()],
            tasks=[self.infrastructure_task(), self.testing_task()],
            process=Process.sequential,
            verbose=True
        )
