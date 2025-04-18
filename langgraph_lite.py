import operator
import json
import os
import httpx
import pandas as pd

from typing import Annotated, Dict, List
from langchain_core.runnables import RunnableLambda
from pydantic import SecretStr
from typing_extensions import TypedDict
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from acquire_access_token import acquire_user_access_token
from dotenv import load_dotenv

# Define a list of agents and their corresponding API URLs
AGENTS = {
    "reconciliation": "https://localhost:4000/api/v1.0/Reconciliation/PerformReconciliation",
    "data_preparation": "https://localhost:4000/api/v2.0/DataPreparationAi/executeDataPreparationPlan"
}

AGENT_DESCRIPTIONS = {
    "reconciliation": "Compares two sets of financial transaction data and finds matches or mismatches.",
    "data_preparation": "Handles data cleaning and preparation tasks to ensure the dataset is ready for downstream processing.",
    "fallback": "This can be used to answer questions around the dataset we are to provide, or any kind of casual questions or when no agent is suitable"
}

class State(TypedDict):
    input: Annotated[str, operator.add]
    selected_agents: Annotated[List[Dict[str, str]], operator.add]
    output: Annotated[dict[str, str], operator.or_]


# Load variables from .env into environment
load_dotenv()

# Access the variable
openai_api_key = os.getenv("OPENAI_API_KEY")

llm = AzureChatOpenAI(
    api_key=SecretStr(openai_api_key),
    azure_endpoint="https://chris-open-ai-service.openai.azure.com/",
    azure_deployment="gpt-4o",
    api_version="2024-12-01-preview",
    temperature=0
)

def get_csv_context(file_path: str) -> str:
    try:
        df = pd.read_csv(file_path)
        return df.to_string(index=False)
    except Exception as e:
        return f"Could not read dataset: {str(e)}"

def router_node(state: State) -> State:
    user_input = state["input"]
    agent_list = "\n".join([f"- {name}: {desc}" for name, desc in AGENT_DESCRIPTIONS.items()])
    prompt = f"""You are an AI assistant that routes user requests to appropriate agents.

    Here are the available agents:
    {agent_list}

    The user may provide a single message that includes multiple requests. Your job is to:
    1. Determine which agent(s) should be invoked.
    2. Split the message into separate tasks for each relevant agent.

    Return your response in the following JSON format:
    [
      {{
        "agent_name": "agent_name",
        "input": "the part of the user input relevant to this agent"
      }},
      ...
    ]

    User message: "{user_input}"

    Only return valid JSON, no explanations.
    """
    response = llm.invoke([HumanMessage(content=prompt)])
    try:
        agents = json.loads(response.content.strip())
        state["selected_agents"] = agents
        return state
    except Exception as e:
        print(f"LLM failed to parse agent names: {e}")
        return state

def reconciliation_node(state: State):
    agent_name = "reconciliation"
    output = state.get("output") or {}
    url = AGENTS.get(agent_name)
    access_token = acquire_user_access_token(config_path="config.json")
    primary_path = "DemoData/BaseReconDemoDataPrimary.csv"
    secondary_path = "DemoData/BaseReconDemoDataSecondary.csv"
    params = {
        "api-version": "2022-03-01-preview"
    }
    files = {
        "PrimaryCsvFile": ("BaseReconDemoDataPrimary.csv", open(primary_path, "rb"), "text/csv"),
        "SecondaryCsvFile": ("BaseReconDemoDataSecondary.csv", open(secondary_path, "rb"), "text/csv"),
    }
    data = {
        "MonetaryKeyStartIndex": "2",
        "PartialColumnIndexValue": "-1"
    }
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    try:
        response = httpx.post(
            url,
            params=params,
            files=files,
            data=data,
            verify=False,
            headers=headers
        )
        response.raise_for_status()
        output[agent_name] = response.json().get("result", response.text)
        state["output"] = output
        return state
    except Exception as e:
        return f"Failed to call agent '{agent_name}': {e}"
    finally:
        # Close opened files
        for file in files.values():
            file[1].close()

def prepare_plan(agent_name, dataprepare_input, headers, file_path) -> str:
    prepare_plan_url = "https://localhost:4000/api/v1.0/DataPreparationAi/generateDataPreparationPlan"

    files = {
        "dataSample": ("BaseReconDemoDataPrimary.csv", open(file_path, "rb"), "text/csv"),
    }
    data = {
        "dataTypes": "[\"DATE\",\"TEXT\",\"TEXT\"]",
        "userPrompt": dataprepare_input
    }
    try:
        response = httpx.post(
            prepare_plan_url,
            files=files,
            data=data,
            verify=False,
            headers=headers
        )
        response.raise_for_status()
        results = response.json().get("result", response.text)
        return results
    except Exception as e:
        return f"Failed to call agent '{agent_name}': {e}"
    finally:
        # Close opened files
        for file in files.values():
            file[1].close()

def dataprepare_node(state: State):
    agent_name = "data_preparation"
    agent = next(t for t in state["selected_agents"] if t["agent_name"] == agent_name)
    dataprepare_input = agent["input"]
    file_path = "DemoData/BaseReconDemoDataPrimary.csv"
    access_token = acquire_user_access_token(config_path="config.json")
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    output = state.get("output") or {}
    url = AGENTS.get(agent_name)
    prepared_plan_as_string = prepare_plan(agent_name, dataprepare_input, headers, file_path)
    prepared_plan = json.dumps(json.loads(prepared_plan_as_string)["dataPreparationPlan"])
    files = {
        "dataToPrepareAsCsv": ("BaseReconDemoDataPrimary.csv", open(file_path, "rb"), "text/csv"),
    }
    data = {
        "dataTypes": "[\"DATE\",\"TEXT\",\"TEXT\"]",
        "dataPreparationPlan": prepared_plan
    }
    try:
        response = httpx.post(
            url,
            files=files,
            data=data,
            verify=False,
            headers=headers
        )
        response.raise_for_status()
        output[agent_name] = response.text
        state["output"] = output
        return state
    except Exception as e:
        return f"Failed to call agent '{agent_name}': {e}"
    finally:
        # Close opened files
        for file in files.values():
            file[1].close()

def fallback_node(state: State) -> State:
    agent_name = "fallback"
    agent = next(t for t in state["selected_agents"] if t["agent_name"] == agent_name)
    user_input = agent["input"]
    primary_path = "DemoData/BaseReconDemoDataPrimary.csv"
    context = get_csv_context(primary_path)
    prompt = f"""
You are a helpful assistant. Use the provided context to answer the user's question.

Context:
{context}

User:
{user_input}
"""
    output = state.get("output") or {}
    response = llm.invoke([HumanMessage(content=prompt)])
    output[agent_name] = response
    state["output"] = output
    return state

def route_to_agents(state: State):
    return [t["agent_name"] for t in state["selected_agents"]]

graph = StateGraph(State)

# Add nodes
graph.add_node("router", RunnableLambda(router_node))
graph.add_node("reconciliation", reconciliation_node)
graph.add_node("data_preparation", dataprepare_node)
graph.add_node("fallback", fallback_node)
# Add edges
graph.set_entry_point("router")

graph.add_conditional_edges(
    "router",
    route_to_agents,
    {
        "reconciliation": "reconciliation",
        "data_preparation": "data_preparation",
        "fallback": "fallback"
    }
)

graph.add_edge("reconciliation", END)
graph.add_edge("data_preparation", END)
graph.add_edge("fallback", END)

# Compile the graph
multiagent_app = graph.compile()

if __name__ == "__main__":
    message = "tell me something about my data"
    result = multiagent_app.invoke({"input": message})
    output = result["output"]
    print("Final fallback response:", output["fallback"])
    print("Final data preparation:", output["data_preparation"])
    print("Final reconciliation:", output["reconciliation"])