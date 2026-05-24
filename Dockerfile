# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster
# Set the working directory in the container to /app
WORKDIR /app
# Copy current directory contents into the container at /app
COPY . /app
# Install any needed packages specified in requirements.txt
RUN pip3 install --trusted-host pypi.python.org -r requirements.txt
# Expose port 5000 and map it to port 5000 on the host machine
EXPOSE 5000
# Run app.py when the container launches
CMD ["python", "app.py"]