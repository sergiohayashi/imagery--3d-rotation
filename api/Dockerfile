# Use an official Python runtime as a parent image
#FROM python:3.9-slim-buster
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory in the container
#WORKDIR /app
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /app
#COPY ./app /app
COPY ./app /usr/src/app/app

# Install any needed packages specified in requirements.txt
#COPY requirements.txt /app
COPY requirements.txt /usr/src/app
COPY global-bundle.pem /usr/src/app
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Run the command to start uVicorn server
CMD ["uvicorn", "app.web.main:app", "--host", "0.0.0.0", "--port", "80"]
#CMD ["tail", "-f", "/dev/null"]
