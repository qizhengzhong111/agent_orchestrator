# Documentation

## 1. Project Structure

```
LG_lite:
├── DemoData                 # csv files for data preparation agent and reconciliation agent
├── config.json              # configuration for getting access tokens
├── acquire_access_token.py  # get access token
├── langgraph_lite.py        # agent structure
├── multiagentchat.py        # fast api for start up this project 
├── requirements.txt         # python lib
├── README.md                # Documentation
```

## 2. Core model details

### 2.1 langgraph_lite.py
We have a router and 3 agents.

router: Understand user input and create a list of agent names

According to the agent names, it would conditionally invoke corresponding agents: `data preparation agent`, `reconciliation agent` and `fallback agent`.

> `data preparation agent` and `reconciliation agent` are `Finance for Copilot` specific agent, if you are not an C4F engineer, you may consider replace these two agent with other agent that you have access to.

```Python
graph = StateGraph(State)

graph.add_node("router", RunnableLambda(router_node))
graph.add_node("reconciliation", reconciliation_node)
graph.add_node("data_preparation", dataprepare_node)
graph.add_node("fallback", fallback_node)

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
```

![graph.png](graph.png)

### 2.2 multiagentchat.py
This defines a simple fastApi which create a service exposed to external client.
You can start the service by running following command in the terminal.
````commandline
uvicorn multiagentchat:app --port 8001
````

### 2.3 .env
You have to create `.env` file and define `OPENAI_API_KEY`, this is used to connect to the open ai api.
You can create the key by creating the model deployment in 
[Azure openai service](https://learn.microsoft.com/en-us/azure/ai-services/openai/).

### 2.4 config.json
> This configuration is very specific for `data preparation agent` and `reconciliation agent`. 
> If you don't have these agents, you should remove it from the `graph`.

### 2.5 DemoData
Dataset that is used by `data preparation agent` and `reconciliation agent`.


Create venv with requirements
