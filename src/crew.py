import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import FileWriterTool

@CrewBase
class EmpresaSoftwareCrew:
    """EmpresaSoftwareCrew crew"""
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self):
        self.llm = self.configurar_llm()

    def configurar_llm(self):
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
            tools=[FileWriterTool()],
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )

    @agent
    def devops_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['devops_agent'],
            tools=[FileWriterTool()],
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )

    @task
    def coding_task(self) -> Task:
        return Task(
            config=self.tasks_config['coding_task'],
            agent=self.backend_agent()
        )

    @task
    def infrastructure_task(self) -> Task:
        return Task(
            config=self.tasks_config['infrastructure_task'],
            agent=self.devops_agent(),
            context=[self.coding_task()]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the EmpresaSoftwareCrew crew"""
        return Crew(
            agents=self.agents, # Automatically collected by the @agent decorator
            tasks=self.tasks,   # Automatically collected by the @task decorator
            process=Process.sequential,
            verbose=True,
        )
