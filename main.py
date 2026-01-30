import os
import sys
import time
from dotenv import load_dotenv
from src.crew import EmpresaSoftwareCrew

# Load environment variables
load_dotenv()

def executar_fluxo(inputs):
    """
    Executes the crew with retry logic.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Starting execution (Attempt {attempt + 1}/{max_retries})...")
            # Instantiate the crew
            software_crew = EmpresaSoftwareCrew()
            crew_instance = software_crew.crew()

            # Kickoff the crew
            result = crew_instance.kickoff(inputs=inputs)

            print("\n################################################")
            print("## Execution Completed Successfully")
            print("################################################\n")
            print(result)
            return result

        except Exception as e:
            print(f"Error during execution: {e}")
            if attempt < max_retries - 1:
                print("Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print("Max retries reached. Execution failed.")
                raise e

def main():
    print("Welcome to EmpresaSoftwareCrew")

    # Ensure output directory exists
    if not os.path.exists('output'):
        os.makedirs('output')

    # Define inputs for the smoke test
    inputs = {
        'topic': 'Controle de Aportes Financeiros',
        'requirements': (
            "Create a simple FastAPI microservice to manage financial contributions (aportes). "
            "It should allow registering a contribution with amount, user_id, and date. "
            "It should also allow retrieving contributions by user_id. "
            "Use SQLite for persistence. "
            "Ensure the code is modular, uses Pydantic for validation, and follows best practices."
        )
    }

    try:
        executar_fluxo(inputs)
    except Exception as e:
        sys.exit(1)

if __name__ == "__main__":
    main()
