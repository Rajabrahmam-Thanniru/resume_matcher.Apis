# Resume API

## Project Structure
- `app/`: Main application folder
- `app/main.py`: Entry point for the FastAPI server
- `app/routers/`: API endpoints separated by feature
- `app/core/`: Settings, configurations, and security functions
- `environment.yml`: Conda dependencies

## How to run
1. Ensure your conda environment is activated.
2. Run the server using uvicorn:
   `uvicorn app.main:app --reload`
