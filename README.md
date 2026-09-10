# ByteSona — AI-Powered News Aggregation and Sentiment Analysis

## Overview

ByteSona is an AI-powered news aggregation and sentiment analysis system that collects news from multiple sources, processes the articles, analyzes their sentiment using a Large Language Model (LLM), and makes the collected information accessible through an AI-powered chatbot.

The main idea behind the project is to go beyond simply collecting and displaying news. ByteSona processes the articles to understand their content and sentiment, stores them in a searchable knowledge base, and allows users to interact with the news using natural language.

The chatbot uses Retrieval-Augmented Generation (RAG) to retrieve relevant news articles from the stored knowledge base before generating a response. This allows the chatbot to answer questions based on the news that has actually been collected by the system.

---

## Key Features

* News aggregation from multiple sources
* Automated news processing and cleaning
* LLM-based sentiment analysis
* News classification based on sentiment
* Text embedding generation
* Vector-based semantic search
* PostgreSQL with pgvector for storing and retrieving embeddings
* RAG-based conversational chatbot
* Context-aware answers based on the collected news
* Storage of article metadata along with processed content

---

## System Architecture

```text
                    News Sources
                         |
                         v
                +------------------+
                |  News Aggregator |
                +--------+---------+
                         |
                         v
                +------------------+
                | News Preprocessing|
                +--------+---------+
                         |
              +----------+----------+
              |                     |
              v                     v
      +---------------+     +------------------+
      | LLM Sentiment |     | Embedding Model  |
      |    Analysis   |     |                  |
      +-------+-------+     +--------+---------+
              |                      |
              v                      v
      +---------------+     +------------------+
      |   Sentiment   |     | Vector Database  |
      |    Metadata   |     |   PostgreSQL +   |
      |               |     |     pgvector     |
      +---------------+     +--------+---------+
                                      |
                                      v
                              +---------------+
                              | RAG Retrieval |
                              +-------+-------+
                                      |
                                      v
                              +---------------+
                              |      LLM      |
                              |    Chatbot    |
                              +-------+-------+
                                      |
                                      v
                                  User Answer
```

---

## How the System Works

The ByteSona pipeline consists of several stages. News is first collected from external sources and then passed through a processing pipeline. The processed content is analyzed for sentiment, converted into embeddings, and stored in the database. The chatbot can then retrieve relevant articles and use them as context when answering user questions.

### 1. News Collection

The first stage of the system is responsible for collecting news articles from configured news sources.

Depending on the source, the system retrieves information such as:

```text
Title
Description
Content
Source
Author
Publication Date
URL
Category
```

The collected data is passed to the preprocessing stage before being used for further analysis.

---

### 2. News Preprocessing

News obtained from external sources can contain HTML elements, unnecessary formatting, duplicated information, or incomplete content.

The preprocessing stage prepares the articles for analysis by cleaning and structuring the data.

This stage can include:

* Removing unnecessary HTML and markup
* Cleaning article text
* Normalizing content
* Handling missing fields
* Removing duplicate articles
* Extracting useful metadata
* Splitting long articles into smaller chunks when required

The result is a cleaner representation of the article that can be passed to the AI components.

---

# LLM-Based Sentiment Analysis

A major component of ByteSona is its LLM-based sentiment analysis.

The system sends the processed news content to an LLM along with instructions describing the type of analysis required. The model reads the article and determines the overall sentiment based on the context of the article rather than simply looking for individual positive or negative words.

The general flow is:

```text
Processed News Article
          |
          v
     LLM Prompt
          |
          v
         LLM
          |
          v
  Sentiment Analysis
          |
          v
Positive / Negative / Neutral
```

For example, consider the following article:

```text
The company reported a 40% increase in revenue,
but its stock declined following weak future guidance.
```

A simple keyword-based approach could find both positive and negative words without understanding how they relate to the actual event.

An LLM can interpret the complete statement and understand that, although the company reported strong revenue growth, the market reaction was negative because of the weak guidance.

This contextual understanding is one of the reasons an LLM is used for sentiment analysis in ByteSona.

The sentiment result can then be stored along with the article and used by other parts of the system.

---

## Why Use an LLM for Sentiment Analysis?

News articles often contain multiple events and opinions within the same piece of content. The sentiment may also depend heavily on context.

For example:

```text
The government increased spending on infrastructure,
although concerns remain about the growing fiscal deficit.
```

The article contains both positive and negative aspects. Determining its overall sentiment requires understanding the relationship between these statements.

An LLM can analyze the article as a whole and use the surrounding context to determine the overall sentiment.

This makes the approach useful for different types of news, including:

* Business
* Finance
* Technology
* Economics
* Politics
* Global events

---

# Embedding Generation

After the news has been processed, the article content is converted into vector embeddings.

An embedding is a numerical representation of the semantic meaning of a piece of text.

The process can be represented as:

```text
News Article
     |
     v
Embedding Model
     |
     v
Vector Representation
```

For example, the following two sentences have different wording but similar meanings:

```text
"Apple launched a new AI-powered device."

"Apple introduced new hardware focused on artificial intelligence."
```

A semantic embedding model can represent these sentences as vectors that are relatively close to each other.

This allows ByteSona to search for information based on meaning rather than only matching exact keywords.

---

# Vector Database

The generated embeddings are stored in a vector-enabled database.

ByteSona uses PostgreSQL with pgvector to store the news data and perform vector similarity searches.

A stored news record can contain information such as:

```text
Article ID
Title
Content
Source
URL
Publication Date
Category
Sentiment
Embedding
```

The embedding is particularly important for the chatbot because it allows the system to find articles that are semantically related to a user's question.

---

# RAG-Based Chatbot

The chatbot is built using Retrieval-Augmented Generation (RAG).

The purpose of RAG is to give the LLM relevant information from the ByteSona news database before it generates an answer.

Instead of relying entirely on the LLM's pre-trained knowledge, the system first searches its own news collection for relevant information.

The chatbot does not simply send this question directly to the LLM.

Instead, the question is first converted into an embedding.

The question vector is then compared with the embeddings stored in the PostgreSQL/pgvector database.

The system retrieves the news articles that are most semantically relevant to the question.

For example:

```text
User Question
      |
      v
Vector Search
      |
      +---- Article 1: AI company launches new model
      |
      +---- Article 2: New AI infrastructure investment
      |
      +---- Article 3: AI startup receives funding
      |
      v
Relevant Context
```

These retrieved articles are then provided to the LLM along with the user's original question.

The LLM uses this retrieved context to generate the final response.

---

## Why RAG is Used

A normal LLM may not have access to the latest news collected by ByteSona. Its knowledge may also not contain the specific articles stored in the project's database.

RAG solves this by connecting the LLM to the project's own knowledge base.

This provides several advantages:

* Responses are based on the news collected by the system
* Recent articles can be used as context
* Users can ask questions using natural language
* The system does not need to retrain the LLM whenever new articles are added
* Relevant information can be retrieved dynamically

The LLM is therefore used primarily for understanding and generating responses, while the vector database is responsible for finding the relevant information.

---

# End-to-End Workflow

The complete ByteSona workflow can be summarized as follows:

```text
1. Fetch News
       |
       v
2. Clean and Process Articles
       |
       +----------------------+
       |                      |
       v                      v
3. LLM Sentiment        4. Generate
   Analysis                 Embeddings
       |                      |
       v                      v
5. Store Metadata      6. Store Vectors
       |                      |
       +----------+-----------+
                  |
                  v
          News Knowledge Base
                  |
                  |
            User Question
                  |
                  v
          Generate Query Vector
                  |
                  v
          Semantic Vector Search
                  |
                  v
         Retrieve Relevant News
                  |
                  v
          Build RAG Context
                  |
                  v
              LLM Chatbot
                  |
                  v
            Final Response
```

| Chatbot Architecture | Retrieval-Augmented Generation (RAG) |

---

# Project Goals

The primary goal of ByteSona is to create a system that does more than aggregate news.

The project combines information retrieval and generative AI to create a pipeline where:

```text
News
  ↓
Processing
  ↓
Understanding
  ↓
Semantic Storage
  ↓
Retrieval
  ↓
AI-powered Interaction
```

This makes the collected news usable as an interactive knowledge base rather than just a collection of articles.

---

# Future Improvements

Some potential improvements to the system include:

* More news sources and categories
* Improved duplicate detection
* More detailed sentiment scoring
* Entity and topic extraction
* News clustering
* Personalized news recommendations
* Source credibility analysis
* Time-based trend analysis
* Improved citation and source attribution in chatbot responses
* Conversation memory for the chatbot
* Real-time news ingestion and analysis

---

