import inspect
from agno.agent import Agent

print(f"Agent.__init__ arguments: {inspect.signature(Agent.__init__)}")
