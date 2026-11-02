"""Explicit registry dispatch for typed preparation tasks, separate from workers."""

from agent_system import telemetry
from agent_system.config import ConfigurationError


class AuthoringDispatcher:
    def __init__(self, *, registry, llm_factory, skills, contracts, context_budget,
                 agent_factory):
        self.registry = registry
        self.llm_factory = llm_factory
        self.skills = skills
        self.contracts = dict(contracts)
        self.context_budget = context_budget
        self.agent_factory = agent_factory
        # Validate every registered authoring capability before constructing clients.
        for name in self.contracts:
            config = self._config(name)
            llm_factory.validate_settings(config.profile, config.settings)

    def _config(self, name):
        if name not in self.contracts:
            raise ConfigurationError('Authoring task has no registered output contract')
        config = self.registry.get(name)
        category, _ = self.contracts[name]
        if (config.category != category or config.mode != 'PREPARATION' or
                config.expected_output != 'CHANGE_PROPOSAL' or
                set(config.tools) - {'search_documents'} or
                set(config.skills) - self.skills.keys()):
            raise ConfigurationError('Authoring agent violates its registered task contract')
        return config

    @telemetry.traced('authoring.delegate', 'generation', inputs=lambda self, name, prompt: {
        'agent': name, 'profile': self._config(name).profile, 'prompt': prompt})
    def run(self, name, prompt):
        config = self._config(name)
        if (config.profile == 'local' and self.context_budget is not None and
                len(prompt) > self.context_budget):
            raise ValueError('Required authoring context exceeds configured budget')
        _, output_type = self.contracts[name]
        agent = self.agent_factory(
            role=config.name, goal='Produce the assigned typed authoring proposal for human review.',
            backstory=config.system_prompt,
            llm=self.llm_factory(config.profile, config.settings),
            tools=[], skills=[self.skills[name] for name in config.skills] or None,
            allow_delegation=False,
        )
        result = getattr(agent.kickoff(prompt, response_format=output_type), 'pydantic', None)
        if type(result) is not output_type:
            raise ValueError('Invalid structured authoring output')
        return output_type.model_validate(result.model_dump(mode='json'))
