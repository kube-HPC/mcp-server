# Accessing Job or Task Logs

## Purpose
This resource guides the assistant (LLM) on how to retrieve and display HKube job logs using available tools and Elasticsearch queries.

---

## Procedure

1. **Find the Job**
   - Use the **job search tool** to locate the job requested by the user (by name, ID, or status).
   - Retrieve the job’s `graph`, which includes the `nodes` array.

2. **Extract Task IDs**
   - Each node in the graph includes a `taskId` field — a unique identifier for the node’s execution task.
   - Collect all `taskId` values from `job.graph.nodes`.

3. **Query Logs from Elasticsearch**
   - For each `taskId`, send a query to Elasticsearch using `meta.internal.taskId` as the filter key.
   - Example query:
```json
{
  "query": {
    "match": {
      "meta.internal.taskId": {
        "query": "kkkeuyw5",
        "type": "phrase"
      }
    }
  }
}
```
   - You should go to endpoint of /_search (example: http://elasticsearch:9200/_search).
   - Expected response fields:
     - `message`: log text.
     - `meta.timestamp`: time the log was created.

4. **Display Log Information**
   - Present logs grouped by node or task ID.
   - Show `meta.timestamp` followed by the `message` for clarity.

---

## Field Definitions
| Field | Description |
|:------|:-------------|
| `taskId` | Unique identifier of the task within the job. |
| `message` | Log content text emitted by the algorithm. |
| `meta.timestamp` | Timestamp when the log entry was recorded. |

---

## Error Handling
- If a job is not found, inform the user and suggest verifying the job name or ID.
- If Elasticsearch query fails, retry once or display an error message explaining the issue.
- If no logs are returned, clarify that no entries were found for the given `taskId`.

---

## Performance Tips
- Limit queries to specific `taskId`s to reduce result size.
- Use filters for time ranges (e.g., `@timestamp`) when possible.
- Avoid fetching all logs at once for large jobs — paginate if supported.

---

## Summary
When a user asks for job logs:
**search job → extract task IDs → query logs → display timestamp + message grouped by task ID.**
