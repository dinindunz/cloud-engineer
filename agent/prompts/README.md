# Cloud Engineer Agent Prompts

This directory contains the organized prompt structure for the multi-agent cloud engineer platform.

## Directory Structure

```
prompts/
├── system/
│   └── orchestrator.md          # Main orchestrator system prompt
└── agents/
    ├── knowledge_base.md        # Knowledge Base Agent prompt
    ├── error_analysis.md        # Error Analysis Agent prompt
    ├── jira.md                  # JIRA Agent prompt
    ├── pr.md                    # PR Agent prompt
    └── operations.md            # Operations Agent prompt
```

## Agent Responsibilities

### System Level
- **orchestrator.md**: Coordinates all 5 specialized agents, handles task delegation, workflow orchestration, and response synthesis

### Agent Level
- **knowledge_base.md**: AWS documentation search and best practices guidance
- **error_analysis.md**: CloudWatch log analysis and error diagnosis with solution recommendations
- **jira.md**: Project management and structured ticket creation for infrastructure issues
- **pr.md**: GitHub repository and pull request management for infrastructure code changes
- **operations.md**: Direct AWS resource operations, monitoring, scaling, and maintenance

## Best Practices

### Prompt Management
1. **Separation of Concerns**: Each agent has a focused, specific role
2. **Maintainability**: Prompts are stored in separate files for easy updates
3. **Consistency**: All prompts follow the same structure with Implementation Guidelines
4. **Version Control**: Changes to prompts are tracked through git

### Prompt Structure
Each agent prompt follows this format:
```markdown
# Agent Name Prompt

Brief description of the agent's role.

## Implementation Guidelines:

**Section 1**: Specific guidance for core functionality
**Section 2**: Process workflows and procedures
**Section 3**: Output formats and standards
**Section 4**: Quality and safety standards
```

### Updating Prompts
1. Edit the relevant `.md` file in the appropriate directory
2. Test changes in a development environment
3. Deploy updates through the standard CI/CD pipeline
4. Monitor agent performance after prompt updates

## Integration

The prompts are loaded dynamically by `cloud_engineer.py` using:
```python
system_prompt = pathlib.Path("prompts/system/orchestrator.md").read_text()
agent_prompt = pathlib.Path("prompts/agents/[agent_name].md").read_text()
```

This allows for runtime prompt updates without code changes, enabling rapid iteration and improvement of agent behavior.
