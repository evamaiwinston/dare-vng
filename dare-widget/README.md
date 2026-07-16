# dare-widget

Drop-in React component 

## Setup


```bash
git clone https://github.com/evamaiwinston/dare-vng.git
cd dare-vng/dare-widget
npm install
npm run build          # produces dist/ 
```

From frontend project:

```bash
npm install ../dare-vng/dare-widget   # path to dare-widget
```

Peer dependencies: `react` and `react-dom`,
either `^17`, `^18`, or `^19`.


## Running the DARE backend

For local dev, run via Docker from the repo root:

```bash
cd dare-vng
docker compose up --build
```

This builds and starts the API on `http://localhost:7860`

- **It needs a populated `.env` in the repo root** (`OPENAI_API_KEY`,
  `OPENAI_BASE_URL`, `LLM_MODEL`, etc.). 
- Once it's up, point widget's `apiUrl` prop at `http://localhost:7860`.


## Usage

Data comes from RAG call: user question, generated answer, and retrieved chunks. 
Render answer as normal and drop `<DareWidget>` under it with values passed as props. 

```tsx
import { DareWidget } from "dare-widget";

<DareWidget
  apiUrl="http://localhost:7860"   // DARE backend 
  query={question}                 // the user's question
  answer={ragAnswer}                // the RAG response to attribute
  chunks={knowledgeSources}         // the retrieved chunks, shape below
/>
```

Add under the rendered RAG answer. 
It renders nothing until the user clicks 
"Explain this answer" — at that point it calls the backend and
walks itself through loading --> result (or error, with a retry button)

### `chunks` shape

RAG response's retrieved chunks (e.g. `knowledge_sources`).
Only `content` is required:

```ts
{
  content: string;          // the chunk text verbatim **required**
  chunk_id?: string | null;
  document_id?: string | null;
  score?: number | null;    
}
```

## Grant CORS permission 

The backend only accepts requests from origins listed in its `CORS_ORIGINS`
env var (comma-separated) — it defaults to `http://localhost:5173`.

Add frontend's origins to `.env`.

