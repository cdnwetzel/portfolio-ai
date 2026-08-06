# Why I Self-Host (DRAFT — pending Chris's review)

**Note:** Drafted by the AI assistant from existing KB material. Chris reviews before
this indexes.

I run my portfolio's AI stack — LLM inference, vector search, reranking, faithfulness
verification — on hardware in my home office instead of renting cloud GPUs. People ask why.

**Cost is the simple part.** At moderate usage, an A4500 NVLink pair pays for itself in
months versus cloud GPU rental. After that, every query is electricity.

**Control is the real part.** When I own the stack, there is no deprecation notice, no
quota, no surprise pricing tier, no vendor roadmap deciding when my model gets retired.
The T5810 serves the same model tomorrow that it serves today. When something breaks, I
fix the thing, not a support ticket.

**It's also the demonstration.** Anyone can rent an A100 and demo a chatbot. Running the
whole RAG pipeline — embedding, retrieval, reranking, generation, independent
faithfulness verification — on hardware I specced, racked, and administer is itself the
portfolio. The infrastructure answers the question the resume can't: can he actually
build and run this? Yes. It's running.

**Privacy rounds it out.** My knowledge base, my queries, and the verifier's scores never
leave my machines. No third party logs a single prompt — not a policy promise, an
architectural fact.

Self-hosting isn't free — it's a trade: my time, my hardware, my problem when it breaks
at 2 AM. For a portfolio that exists to prove I can run infrastructure, that trade is the
whole point.
