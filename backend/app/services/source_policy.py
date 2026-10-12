"""Application boundary for local source configuration, never invokes collection."""

import logging

from app.repositories.source_policy import SourcePolicyRepository

logger = logging.getLogger("stockinsight.services.source_policy")


class SourcePolicyService:
    def __init__(self, directory):
        self.repository = SourcePolicyRepository(directory)

    def read(self):
        return self.repository.read()

    def save(self, mode, revision):
        policy = self.repository.save(mode, revision)
        logger.info(
            "Collection source policy saved",
            extra={
                "event_data": {
                    "mode": policy.mode,
                    "revision": policy.revision,
                    "actor": "local_admin",
                }
            },
        )
        return policy
