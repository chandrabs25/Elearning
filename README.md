# The Living Textbook: An AI Tutor That Learns About You Like a Teacher and Behaves Like a Book


https://github.com/user-attachments/assets/b08e114e-e69f-4539-8402-3a39c5503d1b


_Srichandra_  
_Feb 05, 2026_

Current AI tutors are just wrappers around a search bar, they forget who you are and treat a textbook like a bag of shredded paper. I wanted to build a "Living Textbook" that feels like a real teacher sitting next to you, one who remembers you struggled with vectors last week and knows that "next" means turning the page, not hallucinating a summary. This system uses a strict knowledge graph and a temporal memory engine to learn you back, tracking your evolving mastery while letting you navigate the entire book simply by talking to it.

## The Problem: "Smart" Chatbots Are Actually Pretty Dumb Teachers

## 1. The Insight Engine: A Teacher That Remembers

This is the heart of the system. Every time you interact, whether you’re asking a doubt, solving an exercise, or answering a quiz, the system creates an Insight.

> **Misconception:** "Student confused mass vs. weight in Exercise 7.3."

> **Competency:** "Student correctly applied the Law of Periods."

These aren’t just logs. They are **temporal memory**. If you were confused yesterday but answered correctly today, the new insight supersedes the old one. The system literally updates its mental model of you in real-time.

When I generate a new quiz for you, it’s not random. The AI looks at your active insights and says, _"Hey, they used to struggle with unit conversions here. Let’s test that specifically."_

### Why Summarization-Based Memory Fails

Most AI applications try to remember you by summarizing past conversations. This sounds reasonable, but it fundamentally breaks when facts change over time. A summary is static; it captures what was true at one moment. But learning is dynamic—your understanding evolves every session.

Consider this example:

- **Day 1:** You answer a question about gravitational force incorrectly, confusing mass with weight.
  - _Summary says:_ "Student struggles with mass vs. weight."

- **Day 3:** You correctly solve three problems distinguishing mass and weight.
  - _Summary now says:_ "Student initially struggled with mass vs. weight but later solved problems correctly."

- **Day 5:** You’re asked about gravitational force again.
  - _The AI reads the summary and thinks you might still be confused, because the summary contains both the old misconception AND the correction. It can’t tell which is "current."_

This leads to hallucinations like: "Remember, you had trouble with this before..." when you’ve already mastered it. The AI is stuck in the past.

**The Insight Engine solves this with explicit supersession.** When you demonstrate competency on Day 3, the old "MISCONCEPTION" insight is marked as superseded by the new "COMPETENCY" insight. The AI only sees active insights—it knows you’ve moved on. No ambiguity, no mixed signals, no hallucination.

When I generate a new quiz for you, it’s not random. The AI looks at your active insights and says, _"Hey, they used to struggle with unit conversions here. Let’s test that specifically."_

## 2. Graph-Based Structured Learning

Instead of letting an LLM guess what to teach, I manually mapped the gravity chapter in class 11 physics textbook into a Knowledge Graph.

Every section (like section in a chapter 7.2 Kepler’s Laws) is a node. Every prerequisite (like 7.1 Introduction or concepts like Newton’s laws) is a literal connection in the database. When you open Section 7.2, the AI is strictly constrained to that node. It can sees only the current content and the explicit prerequisites.

This means:

- **No Hallucinations:** It won’t bring in advanced concepts you haven’t unlocked yet.
- **Pedagogical Flow:** It teaches in the exact order the author intended.
- **Building on prerequisites:** Whenever a student is confused with the current section concepts, the tutor explains the prerequisites and connects them to the current section.
- **Personalized verification:** After teaching each subsection, the AI generates a verification question using the student’s insights from both the current section and prerequisites—targeting their specific weak spots rather than asking generic questions.

The chatbot can still answer the questions not relevant to the current section, but it will redirect the student back to the current concept being taught.

## 3. Navigation by Talking (The "Textbook" Metaphor)

I hated the idea of clicking through menus. I wanted you to just talk to the book.

- "Open the exercises."
- "Take me to the next section."
- "Show me a quiz."

The system understands these natural possibilities. Behind the scenes, every new command is cached, so the response is instant, no waiting for an LLM to think. It feels less like using software and more like flipping through a magic book that does exactly what you tell it. I’m already working on adding Voice Control, so you won’t even have to type. You’ll just say, _"Hey, explain this diagram,"_ and it will.

## From One Chapter to a Lifelong Learning OS

Right now, this is running on Class 11 Physics (Gravitation). But the architecture is universal.

Because the **Insight Engine** is separate from the content, it can travel with you.

- **Class 11:** The system learns you’re a visual learner who struggles with algebra.
- **Class 12:** It carries that knowledge into your Chemistry classes.
- **University:** It helps you navigate Engineering Mechanics because it knows you mastered the basics years ago.

This isn’t just about passing a test. It’s about building a digital extension of your own brain, one that organizes the world’s knowledge into a structure you can actually learn, and remembers your journey so you never have to start from scratch again.

every user will have a node insights, which will record the insights for every section of the chapter and every subsection and every exercise. these insights will be superseded by the new insights, whenever they change. The old insights are deleted, they can be used for tracking the progression.
<img width="3636" height="2435" alt="Kepler&#39;s Laws Insight Flow-2026-02-05-130312" src="https://github.com/user-attachments/assets/6cea2cbf-4534-4d9d-abd0-5b44c8b49eb9" />

This is the tutor graph, whenever the student is confused or new to a section, the tutor explains the prerequisites and explain the connection between the prerequisites and the current section
<img width="5911" height="4050" alt="Untitled diagram-2026-02-07-092915" src="https://github.com/user-attachments/assets/ce6c8d3f-40b9-4424-a513-3cd46bc29566" />



<img width="3636" height="2435" alt="Kepler&#39;s Laws Insight Flow-2026-02-05-130335" src="https://github.com/user-attachments/assets/7297c843-497e-43fb-8ed9-c7e<img width="4655" height="3465" alt="Kepler&#39;s Laws Insight Flow-2026-02-05-130400" src="https://github.com/user-attachments/assets/0c90b8cc-6f50-4305-a4a6-03a90e7d549c" />
86806cd32" />
<img width="8124" height="3465" alt="Kepler&#39;s Laws Insight Flow-2026-02-05-130436" src="https://github.com/user-attachments/assets/acd133d1-c25d-495a-ba45-35e91d11ed60" />
<img width="8192" height="3041" alt="Kepler&#39;s Laws Insight Flow-2026-02-05-130740" src="https://github.com/user-attachments/assets/137f99e0-312d-46cb-ab26-31c421cec6ff<img width="5595" height="2435" alt="Kepler&#39;s Laws Insight Flow-2026-02-05-130830" src="https://github.com/user-attachments/assets/45cea945-0576-4ca2-8841-b82e4861c013" />
" /><img width="8192" height="4837" alt="Kepler&#39;s Laws Insight Flow-2026-02-05-130951" src="https://github.com/user-attachments/assets/e5e3f70a-d229-402d-a6e1-800c23370877" />


<img width="8192" height="1417" alt="Kepler&#39;s Laws Insight Flow-2026-02-05-141733" src="https://github.com/user-attachments/assets/8203421f-7f58-48b8-99f4-2f11<img width="5606" height="4995" alt="Kepler&#39;s Laws Insight Flow-2026-02-05-141940" src="https://github.com/user-attachments/assets/69011169-82a3-49c7-a6ef-d1af9f674659" />
6bad97b7" /><img width="8192" height="2827" alt="Kepler&#39;s Laws Insight Flow-2026-02-05-142147" src="https://github.com/user-attachments/assets/f0b7aa33-9d28-4c53-ade3-d228e98f06ed" />


