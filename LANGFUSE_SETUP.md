# Setting Up Langfuse Monitoring for WorkAR-backend

This document explains how to set up and use Langfuse to monitor Gemini API calls in the WorkAR-backend application.

## What is Langfuse?

[Langfuse](https://langfuse.com) is an open-source observability and evaluation platform for LLM applications. It helps you:

- Monitor model usage, latency, and costs
- Track performance over time
- Debug issues in production
- Evaluate model outputs

## Configuration Steps

### 1. Install Required Packages

The necessary packages are already included in `requirements.txt`:

```
langfuse>=2.0.0
```

Make sure your environment has the latest dependencies by running:

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file in the project root with your Langfuse credentials:

```
# Langfuse Monitoring Configuration
# Get your keys from https://cloud.langfuse.com project settings
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key_here
LANGFUSE_SECRET_KEY=your_langfuse_secret_key_here
# Choose your region
LANGFUSE_HOST=https://cloud.langfuse.com  # EU region
# LANGFUSE_HOST=https://us.cloud.langfuse.com  # US region
```

You can obtain these keys from the Langfuse dashboard after creating an account and a project.

### 3. How the Integration Works

The application automatically initializes Langfuse when starting up. The integration:

1. Loads environment variables from `.env`
2. Sets up the Langfuse client when the application starts
3. Uses the `@observe` decorator on Gemini API calls to track:
   - Model inputs and outputs
   - Token usage
   - Errors and exceptions
   - Processing time

### 4. Viewing Your Data in Langfuse

After the application is running and making calls to Gemini:

1. Log into your [Langfuse account](https://cloud.langfuse.com)
2. Navigate to your project dashboard
3. You should see traces appearing for each call to the Gemini API
4. Explore the traces to see detailed information about each call

## Available Metrics

With this integration, you can track:

- **Input/Output**: The prompts sent to Gemini and the responses
- **Token Usage**: Input, output, and total tokens used
- **Models**: Which Gemini models are being used
- **Errors**: Any failures or exceptions during API calls
- **Latency**: How long each API call takes

## Debugging

If you're not seeing data in Langfuse:

1. Check that your environment variables are set correctly
2. Look for any warnings or errors in the application logs about Langfuse initialization
3. Verify that your Langfuse account and project are set up correctly

## Additional Resources

- [Langfuse Documentation](https://langfuse.com/docs)
- [Google Vertex AI Integration Guide](https://langfuse.com/docs/integrations/google-vertex-ai) 