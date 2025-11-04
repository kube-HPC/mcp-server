# Accessing Job Logs in HKube

## Purpose
This resource instructs the assistant (LLM) how to retrieve and display logs for HKube jobs using available tools and Elasticsearch queries.

---

## Procedure

1. **Find the Job**
   - Use the available **job search tool** to locate the job requested by the user (e.g., by name, ID, or status).
   - The tool should return the job’s graph, including its `nodes` array.

2. **Extract Task IDs**
   - Each node in the job graph contains a field named `taskId`.
   - Collect all `taskId` values from `job.graph.nodes`.

3. **Query Logs from Elasticsearch**
   - For each `taskId`, query Elasticsearch using the field `meta.internal.taskId`.
   - The query should look like:
     ```
     meta.internal.taskId == <taskId>
     ```
   - This will return the logs associated with that task.

4. **Display Log Information**
   - From the Elasticsearch results, extract and show:
     - The `message` field — contains the log text.
     - The `meta.timestamp` field — indicates the time of the log.
   - Present the logs grouped or labeled by their corresponding node or task ID.

---

## Notes
- If the user asks for job logs, always follow this exact procedure:  
  **search job → extract task IDs → query logs → show message + timestamp.**
