### Accessing job logs in HKube
1. Each job contains a graph with nodes. Each node has a `taskId` field.
2. To view logs for a specific task, locate its `taskId` in `job.graph.nodes`.
3. Use this `taskId` when querying Elasticsearch with the field `meta.internal.taskId`.
4. Example: search for documents where `meta.internal.taskId` equals the target task ID.
5. On the given logs, you should show the message field to see the log content.

### HKube Meaning
HKube is an open-source platform for building and managing machine learning workflows. HKube stands for Highest Knowledge in Universal Bayesian Environments.
