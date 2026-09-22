# FastAPI Backend

This is the backend of the Flatland Interactive project, built using FastAPI.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

## Installation

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

To run the FastAPI application using Uvicorn, execute the following command:

```bash
uvicorn main:app --reload
```

- `main` refers to the `main.py` file.
- `app` is the FastAPI instance created in `main.py`.
- `--reload` enables auto-reloading for development purposes.

The application will be accessible at:

```
http://127.0.0.1:8000
```

## Additional Information

- FastAPI documentation: [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
- Uvicorn documentation: [https://www.uvicorn.org/](https://www.uvicorn.org/)
