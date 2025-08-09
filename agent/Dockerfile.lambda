FROM public.ecr.aws/lambda/python:3.13

# Install dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy function code
COPY . .

# Set the CMD to the handler (entrypoint)
CMD ["agent.lambda_handler"]