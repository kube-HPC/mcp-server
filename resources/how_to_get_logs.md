# Accessing HKube Job Logs

## Objective
│ This guide explains how to retrieve and display HKube job logs using available tools and Elasticsearch queries.                                                                                                                  │

---

## Enhanced Procedure

1. **Locating the Job**
   - First use the search job tool to locate the desired job by the user requirements.
   - Utilize the **job search tool** to find the job based on specified parameters (name, ID, or status).
   - Access the job's `graph`, which contains an array of `nodes`.

2. **Extracting Task IDs**
   - Each node in the graph has a `taskId` that uniquely identifies its execution.
   - Compile a list of all `taskId` values from `job.graph.nodes`.

3. **Query Logs from Elasticsearch**
   - You will have to search in the `logstash-*` index. You can use the get indices tool if needed.can you 
   - Filter by Field: Use the field `meta.internal.taskId` to match the extracted `taskId` values.
   - You have to use the Elasticsearch tool (`stdio_search`) which expects those arguments: `index`, `query_body`.
   - The arguments should be as follows:
     - `index`: `logstash-*`
     - `query_body`:  { "query": { "match": { "meta.internal.taskId": "<taskId>" } } }
   - Expected Response Fields:
     - `message`: Contains the log text.
     - `meta.timestamp`: Indicates when the log was recorded.

4. **Display Log Information**
   - Present the retrieved logs, grouped by node.
   - Format the output to show `meta.timestamp` followed by the `message` for better readability.

---

## Field Definitions
| Field | Description                                                           |
|:------|:----------------------------------------------------------------------|
| `taskId` | Unique identifier of the task within the job.                         |
| `message` | Text content of the log emitted by the executing algorithm.           |
| `meta.timestamp` | Timestamp indicating when the log entry was created.                  |

---

## Error Handling Procedures
- Job Not Found: Notify the user and recommend verifying the job name or ID.                                                                                                                                                    │
- Query Failures: Attempt the Elasticsearch query again; if it fails again, provide an error message to the user.                                                                                                               │
- No Logs Returned: Inform the user that no log entries were found for the provided taskId. 

---

## Performance Enhancement Tips
- Limit Elasticsearch queries to specific taskIds to minimize result sizes.                                                                                                                                                     │
- Implement time range filters (like @timestamp) whenever applicable.                                                                                                                                                           │
- Avoid fetching all logs at once for extensive jobs; consider pagination if supported. 

---

## Summary of Steps
1. Search for the job.                                                                                                                                                                                                           │
2. Extract task IDs from the job's graph.                                                                                                                                                                                        │
3. Query the logs using the task IDs.                                                                                                                                                                                            │
4. Display the logs grouped by task ID with timestamps.
