# TREC 2025 Retrieval Frontend

A modern, Google-like search interface built with Next.js 14 and shadcn/ui for the TREC 2025 Information Retrieval track.

## Features

- 🔍 **Google-like Search Interface** - Clean, intuitive design
- 🎯 **Multiple Search Modes** - Lexical, Vector, and Hybrid retrieval
- ⚙️ **Configurable Results** - Adjust top-k parameter (5-50 results)
- 🎨 **Beautiful UI** - Built with shadcn/ui components
- ⚡ **Fast & Responsive** - Next.js 14 with App Router
- 🔐 **Secure** - API key authentication

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Running API server (see `backend/api/`)

### Installation

1. Install dependencies:
```bash
npm install
```

2. Create environment file:
```bash
cp .env.local.example .env.local
```

3. Update `.env.local` with your API configuration:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=your-api-key-here
```

### Development

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production

Build for production:

```bash
npm run build
npm start
```

## Usage

1. **Enter your search query** in the search bar
2. **Select search mode**:
   - **Lexical**: Traditional keyword-based search (BM25)
   - **Vector**: Semantic search using embeddings
   - **Hybrid**: Combines lexical and vector search (recommended)
3. **Adjust top-k** to control the number of results (5-50)
4. **Press Enter or click Search** to retrieve results

## Project Structure

```
frontend-next/
├── app/
│   ├── page.tsx          # Main search page
│   ├── layout.tsx        # Root layout
│   └── globals.css       # Global styles
├── components/
│   ├── search-bar.tsx    # Search input component
│   ├── search-filters.tsx # Mode and top-k controls
│   ├── search-results.tsx # Results display
│   └── ui/               # shadcn/ui components
├── lib/
│   ├── api.ts            # API client
│   ├── types.ts          # TypeScript types
│   └── utils.ts          # Utility functions
└── .env.local.example    # Environment variables template
```

## API Integration

The frontend communicates with the retrieval API at `/api/v1/retrieve`:

- **Authentication**: X-API-Key header
- **Request**: Query text, mode, and top-k
- **Response**: Retrieved segments with scores and metadata

See `lib/api.ts` and `lib/types.ts` for implementation details.

## Technologies

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first CSS
- **shadcn/ui** - Beautiful, accessible components
- **Axios** - HTTP client
- **Lucide React** - Icon library

## License

MIT
