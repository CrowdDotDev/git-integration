# Use the Alpine-based Python image as the base image
FROM python:3.10-alpine

# Set the working directory
WORKDIR /app

# Copy the requirement files into the container
COPY pyproject.toml .

# Install the dependencies and required packages
RUN apk update && apk add --no-cache --virtual=.build-dependencies gcc musl-dev libffi-dev \
    && pip install --no-cache-dir -r pyproject.toml \
    && apk del .build-dependencies

# Copy the project files into the container
COPY . .

# Install the cron package
RUN apk add --no-cache busybox
COPY crowdgit-cron /etc/crontabs/root

# Start the cron service and keep the container running
CMD ["crond", "-f"]