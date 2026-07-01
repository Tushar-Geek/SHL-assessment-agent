# Submission Materials

Submit these two items in the form.

## 1. Public API endpoint URL

After deployment, submit the base service URL, for example:

https://shl-assessment-agent.onrender.com

Before submitting, verify both endpoints are reachable:

- https://YOUR-SERVICE-URL/health
- https://YOUR-SERVICE-URL/chat

Expected health response:

{"status":"ok"}

Sample chat request body:

{"messages":[{"role":"user","content":"Need a remote Python developer assessment under 45 minutes"}]}

## 2. Approach document

Upload APPROACH.md from this project. It is intentionally concise and covers:

- Architecture and design choices
- Retrieval setup
- Prompt design
- Evaluation approach
- What did not work
- How improvement is measured
- AI tools used

## Fastest Render deployment

1. Push this folder to a public GitHub repository.
2. Open Render and create a new Web Service from that repository.
3. Render will detect render.yaml and use the Dockerfile.
4. Wait for deploy to finish.
5. Open /health and confirm it returns {"status":"ok"}.
6. Send a POST request to /chat and confirm it returns reply, recommendations, and end_of_conversation.
7. Submit the Render base URL in the form.

## Important final check

If the assignment grader expects the full SHL catalog, run this before deployment in an unrestricted network environment:

python scripts/scrape_catalog.py --output data/catalog.json --browser

Then commit the refreshed data/catalog.json and redeploy.
