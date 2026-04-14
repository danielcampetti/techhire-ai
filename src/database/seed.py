"""Populate the TechHire AI database with realistic sample recruitment data."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from src.database.connection import get_db
from src.database.setup import create_tables

_TODAY = datetime(2026, 4, 13)


def _d(days_ago: int) -> str:
    dt = _TODAY - timedelta(days=days_ago)
    return dt.replace(hour=10, minute=0, second=0).isoformat()


# ---------------------------------------------------------------------------
# Job Postings
# ---------------------------------------------------------------------------
_JOB_POSTINGS = [
    {
        "title": "Engenheiro de IA Pleno",
        "company": "TechHire Corp",
        "description": (
            "Buscamos um Engenheiro de IA Pleno para integrar nosso time de produtos "
            "inteligentes. Você será responsável por desenvolver e manter pipelines de RAG, "
            "fine-tuning de LLMs, APIs de inferência e integrações com modelos de linguagem "
            "de grande escala. Trabalhará com arquiteturas multi-agente e sistemas de "
            "recuperação vetorial."
        ),
        "requirements": (
            "Python 3.10+, FastAPI, Docker, ChromaDB ou similar, experiência com LLMs "
            "(OpenAI, Anthropic, Ollama), RAG pipelines, embeddings, 3+ anos de experiência"
        ),
        "desired_skills": "LangChain, LangGraph, AWS, Kubernetes, MLflow, PyTorch, transformers",
        "seniority_level": "pleno",
        "work_model": "remote",
        "salary_range": "R$ 12.000 – R$ 18.000",
    },
    {
        "title": "Desenvolvedor Backend Sênior",
        "company": "TechHire Corp",
        "description": (
            "Procuramos um Desenvolvedor Backend Sênior para liderar o desenvolvimento de "
            "APIs robustas e escaláveis. O profissional irá projetar microsserviços, garantir "
            "alta disponibilidade e mentorear desenvolvedores júnior. Experiência com bancos "
            "de dados relacionais e NoSQL é essencial."
        ),
        "requirements": (
            "Python ou Node.js, REST APIs, PostgreSQL, Redis, Docker, 5+ anos de experiência, "
            "testes automatizados, CI/CD"
        ),
        "desired_skills": "AWS, Kafka, Kubernetes, GraphQL, Go, TypeScript",
        "seniority_level": "senior",
        "work_model": "hybrid",
        "salary_range": "R$ 15.000 – R$ 22.000",
    },
]

# ---------------------------------------------------------------------------
# Candidates (20 total)
# Group 1 (IDs 1-5): AI/ML engineers — strong match for job 1
# Group 2 (IDs 6-10): backend developers — strong match for job 2
# Group 3 (IDs 11-15): frontend developers — weak match for both
# Group 4 (IDs 16-20): data analysts — moderate match for job 1
# ---------------------------------------------------------------------------
_CANDIDATES = [
    # --- AI/ML Engineers (1-5) ---
    {
        "full_name": "Lucas Mendes Ferreira",
        "email": "lucas.ferreira@email.com",
        "phone": "(11) 99123-4567",
        "cpf": "123.456.789-00",
        "location": "São Paulo, SP",
        "current_role": "Engenheiro de Machine Learning",
        "experience_years": 5,
        "education": "Mestrado em Ciência da Computação – USP",
        "skills": json.dumps(["Python", "RAG", "LLMs", "FastAPI", "Docker", "ChromaDB",
                               "PyTorch", "transformers", "LangChain", "AWS"]),
        "resume_filename": "lucas_mendes_ferreira.pdf",
        "resume_text": (
            "Lucas Mendes Ferreira — Engenheiro de Machine Learning\n"
            "São Paulo, SP | lucas.ferreira@email.com | (11) 99123-4567\n\n"
            "RESUMO PROFISSIONAL\n"
            "5 anos de experiência em projetos de IA e Machine Learning. Especialista em "
            "pipelines RAG, LLMs e sistemas de recuperação vetorial. Forte background em "
            "Python e FastAPI para APIs de inferência.\n\n"
            "EXPERIÊNCIA\n"
            "Engenheiro de ML Sênior — FinTech S.A. (2022–atual)\n"
            "- Desenvolveu pipeline RAG com ChromaDB e LLaMA para Q&A sobre documentos internos\n"
            "- Implementou fine-tuning de modelos Mistral para domínio financeiro\n"
            "- Construiu APIs FastAPI para servir modelos em produção (Docker + AWS ECS)\n"
            "- Reduziu latência de inferência em 40% com prompt caching e quantização\n\n"
            "Cientista de Dados — DataCorp (2019–2022)\n"
            "- Modelos de classificação e regressão com scikit-learn e PyTorch\n"
            "- Pipelines ETL com Apache Airflow\n\n"
            "FORMAÇÃO\n"
            "Mestrado em Ciência da Computação — USP (2019)\n"
            "Bacharelado em Engenharia da Computação — UNICAMP (2017)\n\n"
            "HABILIDADES\n"
            "Python, RAG, LLMs, FastAPI, Docker, ChromaDB, PyTorch, transformers, "
            "LangChain, LangGraph, AWS, MLflow, embeddings, sentence-transformers"
        ),
    },
    {
        "full_name": "Isabela Costa Rodrigues",
        "email": "isabela.rodrigues@email.com",
        "phone": "(21) 98234-5678",
        "cpf": "234.567.890-11",
        "location": "Rio de Janeiro, RJ",
        "current_role": "Pesquisadora em NLP",
        "experience_years": 4,
        "education": "Doutorado em NLP – PUC-Rio",
        "skills": json.dumps(["Python", "NLP", "LLMs", "RAG", "FastAPI", "Docker",
                               "Hugging Face", "transformers", "embeddings", "ChromaDB"]),
        "resume_filename": "isabela_costa_rodrigues.pdf",
        "resume_text": (
            "Isabela Costa Rodrigues — Pesquisadora em NLP\n"
            "Rio de Janeiro, RJ | isabela.rodrigues@email.com\n\n"
            "RESUMO\n"
            "Doutora em NLP com 4 anos de experiência em pesquisa e aplicações industriais. "
            "Expertise em modelos de linguagem, embeddings e sistemas RAG para português.\n\n"
            "EXPERIÊNCIA\n"
            "Pesquisadora Sênior — AI Lab Brasil (2021–atual)\n"
            "- Desenvolveu modelos de embeddings para português brasileiro (publicado no ACL)\n"
            "- Arquitetura RAG para assistentes de compliance financeiro\n"
            "- FastAPI + Docker para deploy de modelos em nuvem\n"
            "- Liderou equipe de 4 pesquisadores\n\n"
            "FORMAÇÃO\n"
            "Doutorado em NLP — PUC-Rio (2021)\n"
            "Mestrado em IA — UFMG (2018)\n\n"
            "HABILIDADES\n"
            "Python, NLP, LLMs, RAG, FastAPI, Docker, Hugging Face, transformers, "
            "embeddings, ChromaDB, sentence-transformers, BERT, GPT"
        ),
    },
    {
        "full_name": "Rafael Oliveira Lima",
        "email": "rafael.lima@email.com",
        "phone": "(31) 97345-6789",
        "cpf": "345.678.901-22",
        "location": "Belo Horizonte, MG",
        "current_role": "Engenheiro de IA",
        "experience_years": 3,
        "education": "Bacharelado em Engenharia de Software – UFMG",
        "skills": json.dumps(["Python", "FastAPI", "Docker", "LLMs", "Ollama",
                               "PostgreSQL", "Redis", "AWS", "CI/CD"]),
        "resume_filename": "rafael_oliveira_lima.pdf",
        "resume_text": (
            "Rafael Oliveira Lima — Engenheiro de IA\n"
            "Belo Horizonte, MG | rafael.lima@email.com\n\n"
            "RESUMO\n"
            "3 anos de experiência construindo sistemas de IA com foco em LLMs e APIs. "
            "Especialista em integração de modelos Ollama e Anthropic Claude com backends FastAPI.\n\n"
            "EXPERIÊNCIA\n"
            "Engenheiro de IA — StartupAI (2023–atual)\n"
            "- Integrou Ollama (llama3, mistral) com FastAPI para chatbots corporativos\n"
            "- Criou sistema RAG usando FAISS e ChromaDB\n"
            "- Deploy com Docker Compose e GitHub Actions CI/CD\n\n"
            "Desenvolvedor Backend — TechMinas (2021–2023)\n"
            "- APIs REST com FastAPI e PostgreSQL\n"
            "- Cache com Redis, testes com pytest\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Engenharia de Software — UFMG (2021)\n\n"
            "HABILIDADES\n"
            "Python, FastAPI, Docker, LLMs, Ollama, ChromaDB, RAG, PostgreSQL, "
            "Redis, AWS, CI/CD, pytest"
        ),
    },
    {
        "full_name": "Ana Beatriz Souza",
        "email": "ana.souza@email.com",
        "phone": "(11) 96456-7890",
        "cpf": "456.789.012-33",
        "location": "Campinas, SP",
        "current_role": "Cientista de Dados / IA",
        "experience_years": 6,
        "education": "Mestrado em IA – UNICAMP",
        "skills": json.dumps(["Python", "PyTorch", "TensorFlow", "MLflow", "Docker",
                               "FastAPI", "LLMs", "RAG", "AWS", "Kubernetes"]),
        "resume_filename": "ana_beatriz_souza.pdf",
        "resume_text": (
            "Ana Beatriz Souza — Cientista de Dados / Engenheira de IA\n"
            "Campinas, SP | ana.souza@email.com\n\n"
            "RESUMO\n"
            "6 anos de experiência em ML e IA. Liderou projetos de LLMs em produção "
            "usando PyTorch, MLflow e AWS SageMaker.\n\n"
            "EXPERIÊNCIA\n"
            "Tech Lead de IA — BigTech BR (2020–atual)\n"
            "- Liderou migração para arquitetura RAG com LLaMA 2 e ChromaDB\n"
            "- MLflow para rastreamento de experimentos e model registry\n"
            "- Kubernetes para orquestração de pipelines de inferência\n"
            "- Mentorou equipe de 8 cientistas de dados\n\n"
            "FORMAÇÃO\n"
            "Mestrado em IA — UNICAMP (2018)\n\n"
            "HABILIDADES\n"
            "Python, PyTorch, TensorFlow, MLflow, Docker, FastAPI, LLMs, RAG, "
            "AWS SageMaker, Kubernetes, embeddings, RLHF"
        ),
    },
    {
        "full_name": "Thiago Alves Nunes",
        "email": "thiago.nunes@email.com",
        "phone": "(41) 95567-8901",
        "cpf": "567.890.123-44",
        "location": "Curitiba, PR",
        "current_role": "Engenheiro de Machine Learning",
        "experience_years": 4,
        "education": "Bacharelado em Ciência da Computação – UFPR",
        "skills": json.dumps(["Python", "LangChain", "LangGraph", "FastAPI", "Docker",
                               "RAG", "OpenAI", "Anthropic", "embeddings", "PostgreSQL"]),
        "resume_filename": "thiago_alves_nunes.pdf",
        "resume_text": (
            "Thiago Alves Nunes — Engenheiro de Machine Learning\n"
            "Curitiba, PR | thiago.nunes@email.com\n\n"
            "RESUMO\n"
            "4 anos construindo sistemas multi-agente com LangChain e LangGraph. "
            "Experiência sólida com APIs OpenAI e Anthropic Claude em produção.\n\n"
            "EXPERIÊNCIA\n"
            "Engenheiro de ML — AgentLabs (2022–atual)\n"
            "- Sistemas multi-agente com LangGraph para automação de processos\n"
            "- Pipelines RAG com LangChain, OpenAI embeddings e pgvector\n"
            "- Deploy com FastAPI, Docker e GitHub Actions\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Ciência da Computação — UFPR (2022)\n\n"
            "HABILIDADES\n"
            "Python, LangChain, LangGraph, FastAPI, Docker, RAG, OpenAI, "
            "Anthropic Claude, embeddings, PostgreSQL, pgvector"
        ),
    },
    # --- Backend Developers (6-10) ---
    {
        "full_name": "Mariana Torres Gomes",
        "email": "mariana.gomes@email.com",
        "phone": "(11) 94678-9012",
        "cpf": "678.901.234-55",
        "location": "São Paulo, SP",
        "current_role": "Desenvolvedora Backend Sênior",
        "experience_years": 7,
        "education": "Bacharelado em Sistemas de Informação – FIAP",
        "skills": json.dumps(["Python", "FastAPI", "PostgreSQL", "Redis", "Docker",
                               "AWS", "Kafka", "Kubernetes", "CI/CD", "REST APIs"]),
        "resume_filename": "mariana_torres_gomes.pdf",
        "resume_text": (
            "Mariana Torres Gomes — Desenvolvedora Backend Sênior\n"
            "São Paulo, SP | mariana.gomes@email.com\n\n"
            "RESUMO\n"
            "7 anos desenvolvendo APIs robustas e microsserviços de alta disponibilidade. "
            "Especialista em Python, FastAPI e arquiteturas orientadas a eventos.\n\n"
            "EXPERIÊNCIA\n"
            "Tech Lead Backend — FinBank (2019–atual)\n"
            "- Liderou migração monolito → microsserviços (Python + FastAPI)\n"
            "- Kafka para streaming de eventos financeiros\n"
            "- PostgreSQL + Redis para dados transacionais\n"
            "- Kubernetes em AWS EKS, 99.99% SLA\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Sistemas de Informação — FIAP (2017)\n\n"
            "HABILIDADES\n"
            "Python, FastAPI, PostgreSQL, Redis, Docker, AWS, Kafka, Kubernetes, "
            "CI/CD, REST APIs, GraphQL, testes automatizados"
        ),
    },
    {
        "full_name": "Rodrigo Santos Pereira",
        "email": "rodrigo.pereira@email.com",
        "phone": "(51) 93789-0123",
        "cpf": "789.012.345-66",
        "location": "Porto Alegre, RS",
        "current_role": "Engenheiro Backend",
        "experience_years": 5,
        "education": "Bacharelado em Engenharia da Computação – UFRGS",
        "skills": json.dumps(["Python", "Django", "PostgreSQL", "Docker", "AWS",
                               "REST APIs", "CI/CD", "pytest", "Redis", "Celery"]),
        "resume_filename": "rodrigo_santos_pereira.pdf",
        "resume_text": (
            "Rodrigo Santos Pereira — Engenheiro Backend\n"
            "Porto Alegre, RS | rodrigo.pereira@email.com\n\n"
            "RESUMO\n"
            "5 anos em desenvolvimento backend com Python e Django. "
            "Forte cultura de testes e CI/CD.\n\n"
            "EXPERIÊNCIA\n"
            "Engenheiro Backend — E-commerce Plus (2021–atual)\n"
            "- APIs Django REST com PostgreSQL, Redis e Celery\n"
            "- Pipeline CI/CD com GitHub Actions e AWS CodeDeploy\n"
            "- Cobertura de testes acima de 90% com pytest\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Engenharia da Computação — UFRGS (2019)\n\n"
            "HABILIDADES\n"
            "Python, Django, FastAPI, PostgreSQL, Redis, Celery, Docker, "
            "AWS, CI/CD, pytest, REST APIs"
        ),
    },
    {
        "full_name": "Fernanda Lima Cardoso",
        "email": "fernanda.cardoso@email.com",
        "phone": "(71) 92890-1234",
        "cpf": "890.123.456-77",
        "location": "Salvador, BA",
        "current_role": "Desenvolvedora Backend",
        "experience_years": 6,
        "education": "Bacharelado em Ciência da Computação – UFBA",
        "skills": json.dumps(["Node.js", "TypeScript", "PostgreSQL", "Docker", "AWS",
                               "REST APIs", "GraphQL", "Kafka", "CI/CD", "MongoDB"]),
        "resume_filename": "fernanda_lima_cardoso.pdf",
        "resume_text": (
            "Fernanda Lima Cardoso — Desenvolvedora Backend\n"
            "Salvador, BA | fernanda.cardoso@email.com\n\n"
            "RESUMO\n"
            "6 anos em desenvolvimento backend com Node.js e TypeScript. "
            "Experiência em microsserviços e APIs GraphQL.\n\n"
            "EXPERIÊNCIA\n"
            "Engenheira Backend — HealthTech (2020–atual)\n"
            "- APIs Node.js + TypeScript com GraphQL e PostgreSQL\n"
            "- Kafka para integração entre serviços\n"
            "- AWS Lambda e ECS para deploy serverless e contêineres\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Ciência da Computação — UFBA (2018)\n\n"
            "HABILIDADES\n"
            "Node.js, TypeScript, PostgreSQL, MongoDB, Docker, AWS, "
            "GraphQL, Kafka, CI/CD, REST APIs"
        ),
    },
    {
        "full_name": "Carlos Eduardo Matos",
        "email": "carlos.matos@email.com",
        "phone": "(62) 91901-2345",
        "cpf": "901.234.567-88",
        "location": "Goiânia, GO",
        "current_role": "Desenvolvedor Backend Pleno",
        "experience_years": 4,
        "education": "Bacharelado em Engenharia de Software – UFG",
        "skills": json.dumps(["Python", "FastAPI", "PostgreSQL", "Docker", "AWS",
                               "REST APIs", "pytest", "Redis", "CI/CD"]),
        "resume_filename": "carlos_eduardo_matos.pdf",
        "resume_text": (
            "Carlos Eduardo Matos — Desenvolvedor Backend Pleno\n"
            "Goiânia, GO | carlos.matos@email.com\n\n"
            "RESUMO\n"
            "4 anos em desenvolvimento backend com Python e FastAPI. "
            "Foco em qualidade de código e testes automatizados.\n\n"
            "EXPERIÊNCIA\n"
            "Desenvolvedor Backend — InsurTech GO (2022–atual)\n"
            "- APIs FastAPI com PostgreSQL e Redis\n"
            "- Testes com pytest (80%+ cobertura)\n"
            "- Deploy com Docker e AWS\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Engenharia de Software — UFG (2020)\n\n"
            "HABILIDADES\n"
            "Python, FastAPI, PostgreSQL, Redis, Docker, AWS, pytest, CI/CD, REST APIs"
        ),
    },
    {
        "full_name": "Patricia Almeida Ramos",
        "email": "patricia.ramos@email.com",
        "phone": "(81) 90012-3456",
        "cpf": "012.345.678-99",
        "location": "Recife, PE",
        "current_role": "Engenheira de Software Backend",
        "experience_years": 8,
        "education": "Mestrado em Engenharia de Software – UFPE",
        "skills": json.dumps(["Python", "Go", "PostgreSQL", "Docker", "Kubernetes",
                               "AWS", "Kafka", "REST APIs", "CI/CD", "Redis"]),
        "resume_filename": "patricia_almeida_ramos.pdf",
        "resume_text": (
            "Patricia Almeida Ramos — Engenheira de Software Backend\n"
            "Recife, PE | patricia.ramos@email.com\n\n"
            "RESUMO\n"
            "8 anos em desenvolvimento backend com Python e Go. "
            "Especialista em sistemas distribuídos e alta escala.\n\n"
            "EXPERIÊNCIA\n"
            "Principal Engineer — ScaleTech (2018–atual)\n"
            "- Microsserviços em Go e Python com Kafka\n"
            "- Kubernetes para orquestração de 50+ serviços\n"
            "- Liderou time de 12 engenheiros\n\n"
            "FORMAÇÃO\n"
            "Mestrado em Engenharia de Software — UFPE (2016)\n\n"
            "HABILIDADES\n"
            "Python, Go, PostgreSQL, Docker, Kubernetes, AWS, Kafka, "
            "CI/CD, REST APIs, Redis, sistemas distribuídos"
        ),
    },
    # --- Frontend Developers (11-15) ---
    {
        "full_name": "Juliana Castro Ferreira",
        "email": "juliana.ferreira@email.com",
        "phone": "(11) 89123-4567",
        "cpf": "111.222.333-00",
        "location": "São Paulo, SP",
        "current_role": "Desenvolvedora Frontend Sênior",
        "experience_years": 6,
        "education": "Bacharelado em Design Digital – Mackenzie",
        "skills": json.dumps(["React", "TypeScript", "Next.js", "CSS", "HTML",
                               "Node.js", "GraphQL", "Jest", "Figma"]),
        "resume_filename": "juliana_castro_ferreira.pdf",
        "resume_text": (
            "Juliana Castro Ferreira — Desenvolvedora Frontend Sênior\n"
            "São Paulo, SP | juliana.ferreira@email.com\n\n"
            "RESUMO\n"
            "6 anos em desenvolvimento frontend com React e Next.js. "
            "Forte foco em acessibilidade e performance web.\n\n"
            "EXPERIÊNCIA\n"
            "Frontend Lead — MediaCorp (2020–atual)\n"
            "- Aplicações React + TypeScript com Next.js\n"
            "- Design system com Storybook e Figma\n"
            "- Testes com Jest e Cypress\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Design Digital — Mackenzie (2018)\n\n"
            "HABILIDADES\n"
            "React, TypeScript, Next.js, CSS, HTML, Node.js, GraphQL, "
            "Jest, Cypress, Figma, Storybook"
        ),
    },
    {
        "full_name": "Bruno Nascimento Silva",
        "email": "bruno.silva@email.com",
        "phone": "(21) 88234-5678",
        "cpf": "222.333.444-11",
        "location": "Rio de Janeiro, RJ",
        "current_role": "Desenvolvedor Frontend Pleno",
        "experience_years": 4,
        "education": "Bacharelado em Sistemas de Informação – UFRJ",
        "skills": json.dumps(["React", "JavaScript", "Vue.js", "CSS", "HTML",
                               "Node.js", "REST APIs", "Jest"]),
        "resume_filename": "bruno_nascimento_silva.pdf",
        "resume_text": (
            "Bruno Nascimento Silva — Desenvolvedor Frontend Pleno\n"
            "Rio de Janeiro, RJ | bruno.silva@email.com\n\n"
            "RESUMO\n"
            "4 anos em desenvolvimento frontend com React e Vue.js.\n\n"
            "EXPERIÊNCIA\n"
            "Frontend Developer — WebAgency RJ (2022–atual)\n"
            "- SPAs com React e Vue.js\n"
            "- Consumo de REST APIs e GraphQL\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Sistemas de Informação — UFRJ (2020)\n\n"
            "HABILIDADES\n"
            "React, JavaScript, Vue.js, CSS, HTML, Node.js, REST APIs, Jest"
        ),
    },
    {
        "full_name": "Camila Duarte Mendes",
        "email": "camila.mendes@email.com",
        "phone": "(31) 87345-6789",
        "cpf": "333.444.555-22",
        "location": "Belo Horizonte, MG",
        "current_role": "Desenvolvedora Frontend",
        "experience_years": 3,
        "education": "Bacharelado em Engenharia da Computação – PUC Minas",
        "skills": json.dumps(["React", "TypeScript", "Next.js", "Tailwind CSS",
                               "HTML", "CSS", "Jest", "Figma"]),
        "resume_filename": "camila_duarte_mendes.pdf",
        "resume_text": (
            "Camila Duarte Mendes — Desenvolvedora Frontend\n"
            "Belo Horizonte, MG | camila.mendes@email.com\n\n"
            "RESUMO\n"
            "3 anos construindo interfaces com React, Next.js e Tailwind CSS.\n\n"
            "EXPERIÊNCIA\n"
            "Frontend Developer — EdTech MG (2023–atual)\n"
            "- Plataforma educacional com Next.js e TypeScript\n"
            "- UI components com Tailwind CSS e Radix UI\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Engenharia da Computação — PUC Minas (2021)\n\n"
            "HABILIDADES\n"
            "React, TypeScript, Next.js, Tailwind CSS, HTML, CSS, Jest, Figma"
        ),
    },
    {
        "full_name": "Diego Vieira Carvalho",
        "email": "diego.carvalho@email.com",
        "phone": "(41) 86456-7890",
        "cpf": "444.555.666-33",
        "location": "Curitiba, PR",
        "current_role": "Desenvolvedor Frontend",
        "experience_years": 5,
        "education": "Tecnólogo em Análise e Desenvolvimento de Sistemas – UTFPR",
        "skills": json.dumps(["React", "JavaScript", "Angular", "CSS", "HTML",
                               "REST APIs", "Jest", "Docker"]),
        "resume_filename": "diego_vieira_carvalho.pdf",
        "resume_text": (
            "Diego Vieira Carvalho — Desenvolvedor Frontend\n"
            "Curitiba, PR | diego.carvalho@email.com\n\n"
            "RESUMO\n"
            "5 anos em frontend com React e Angular para aplicações enterprise.\n\n"
            "EXPERIÊNCIA\n"
            "Frontend Dev — ERP Solutions PR (2021–atual)\n"
            "- Migração Angular → React para sistema ERP\n"
            "- Consumo de REST APIs com Axios\n\n"
            "FORMAÇÃO\n"
            "Tecnólogo em ADS — UTFPR (2019)\n\n"
            "HABILIDADES\n"
            "React, JavaScript, Angular, CSS, HTML, REST APIs, Jest, Docker"
        ),
    },
    {
        "full_name": "Larissa Pinto Barbosa",
        "email": "larissa.barbosa@email.com",
        "phone": "(51) 85567-8901",
        "cpf": "555.666.777-44",
        "location": "Porto Alegre, RS",
        "current_role": "Desenvolvedora UI/Frontend",
        "experience_years": 4,
        "education": "Bacharelado em Design – UFRGS",
        "skills": json.dumps(["React", "CSS", "Figma", "HTML", "JavaScript",
                               "Storybook", "Accessibility", "UX"]),
        "resume_filename": "larissa_pinto_barbosa.pdf",
        "resume_text": (
            "Larissa Pinto Barbosa — Desenvolvedora UI/Frontend\n"
            "Porto Alegre, RS | larissa.barbosa@email.com\n\n"
            "RESUMO\n"
            "4 anos em design de sistemas e implementação de interfaces React. "
            "Forte foco em acessibilidade e design systems.\n\n"
            "EXPERIÊNCIA\n"
            "UI Engineer — RetailTech RS (2022–atual)\n"
            "- Design system com React e Storybook\n"
            "- Acessibilidade WCAG 2.1 AA\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Design — UFRGS (2020)\n\n"
            "HABILIDADES\n"
            "React, CSS, Figma, HTML, JavaScript, Storybook, Acessibilidade, UX"
        ),
    },
    # --- Data Analysts (16-20) ---
    {
        "full_name": "Eduardo Campos Ribeiro",
        "email": "eduardo.ribeiro@email.com",
        "phone": "(11) 84678-9012",
        "cpf": "666.777.888-55",
        "location": "São Paulo, SP",
        "current_role": "Analista de Dados Sênior",
        "experience_years": 5,
        "education": "Bacharelado em Estatística – USP",
        "skills": json.dumps(["Python", "SQL", "pandas", "scikit-learn", "Tableau",
                               "AWS", "Spark", "dbt", "Airflow", "Power BI"]),
        "resume_filename": "eduardo_campos_ribeiro.pdf",
        "resume_text": (
            "Eduardo Campos Ribeiro — Analista de Dados Sênior\n"
            "São Paulo, SP | eduardo.ribeiro@email.com\n\n"
            "RESUMO\n"
            "5 anos em análise de dados e BI. Conhecimento sólido em Python para "
            "modelagem estatística e ML clássico.\n\n"
            "EXPERIÊNCIA\n"
            "Analista de Dados Sênior — RetailCorp (2021–atual)\n"
            "- Pipelines ETL com Airflow e dbt\n"
            "- Dashboards com Tableau e Power BI\n"
            "- Modelos preditivos com scikit-learn\n"
            "- AWS S3 + Glue para data lake\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Estatística — USP (2019)\n\n"
            "HABILIDADES\n"
            "Python, SQL, pandas, scikit-learn, Tableau, Power BI, "
            "AWS, Spark, dbt, Airflow"
        ),
    },
    {
        "full_name": "Priscila Monteiro Farias",
        "email": "priscila.farias@email.com",
        "phone": "(21) 83789-0123",
        "cpf": "777.888.999-66",
        "location": "Rio de Janeiro, RJ",
        "current_role": "Engenheira de Dados",
        "experience_years": 6,
        "education": "Bacharelado em Ciência da Computação – UFRJ",
        "skills": json.dumps(["Python", "SQL", "Spark", "Kafka", "AWS", "dbt",
                               "Airflow", "PostgreSQL", "Docker", "scikit-learn"]),
        "resume_filename": "priscila_monteiro_farias.pdf",
        "resume_text": (
            "Priscila Monteiro Farias — Engenheira de Dados\n"
            "Rio de Janeiro, RJ | priscila.farias@email.com\n\n"
            "RESUMO\n"
            "6 anos em engenharia de dados e MLOps. Experiência com Python e LLMs "
            "para feature engineering e pré-processamento de texto.\n\n"
            "EXPERIÊNCIA\n"
            "Engenheira de Dados — Telecom RJ (2020–atual)\n"
            "- Pipelines Spark no AWS EMR\n"
            "- Kafka para ingestão de eventos em tempo real\n"
            "- Experimentou RAG com LangChain para relatórios automáticos\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Ciência da Computação — UFRJ (2018)\n\n"
            "HABILIDADES\n"
            "Python, SQL, Spark, Kafka, AWS, dbt, Airflow, Docker, "
            "scikit-learn, LangChain (básico)"
        ),
    },
    {
        "full_name": "Guilherme Araújo Costa",
        "email": "guilherme.costa@email.com",
        "phone": "(48) 82890-1234",
        "cpf": "888.999.000-77",
        "location": "Florianópolis, SC",
        "current_role": "Cientista de Dados",
        "experience_years": 3,
        "education": "Mestrado em Estatística – UFSC",
        "skills": json.dumps(["Python", "R", "scikit-learn", "PyTorch", "SQL",
                               "pandas", "NumPy", "Jupyter", "Matplotlib"]),
        "resume_filename": "guilherme_araujo_costa.pdf",
        "resume_text": (
            "Guilherme Araújo Costa — Cientista de Dados\n"
            "Florianópolis, SC | guilherme.costa@email.com\n\n"
            "RESUMO\n"
            "3 anos em ciência de dados com Python e R. Foco em modelos preditivos "
            "e análise estatística. Interesse em LLMs.\n\n"
            "EXPERIÊNCIA\n"
            "Cientista de Dados — AgroTech SC (2023–atual)\n"
            "- Modelos de previsão de safra com scikit-learn e PyTorch\n"
            "- Análise exploratória com pandas e Matplotlib\n"
            "- Experimentos com modelos de linguagem para análise de sentimentos\n\n"
            "FORMAÇÃO\n"
            "Mestrado em Estatística — UFSC (2022)\n\n"
            "HABILIDADES\n"
            "Python, R, scikit-learn, PyTorch, SQL, pandas, NumPy, Jupyter"
        ),
    },
    {
        "full_name": "Aline Barbosa Nascimento",
        "email": "aline.nascimento@email.com",
        "phone": "(85) 81901-2345",
        "cpf": "999.000.111-88",
        "location": "Fortaleza, CE",
        "current_role": "Analista de Business Intelligence",
        "experience_years": 4,
        "education": "Bacharelado em Administração – UFC",
        "skills": json.dumps(["SQL", "Power BI", "Excel", "Python", "Tableau",
                               "dbt", "MySQL", "Looker"]),
        "resume_filename": "aline_barbosa_nascimento.pdf",
        "resume_text": (
            "Aline Barbosa Nascimento — Analista de BI\n"
            "Fortaleza, CE | aline.nascimento@email.com\n\n"
            "RESUMO\n"
            "4 anos em Business Intelligence. Forte domínio em SQL e ferramentas de "
            "visualização. Python para automação de relatórios.\n\n"
            "EXPERIÊNCIA\n"
            "Analista BI — Varejo CE (2022–atual)\n"
            "- Dashboards Power BI e Looker\n"
            "- Modelagem dimensional com dbt\n"
            "- SQL avançado para ETL\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Administração — UFC (2020)\n\n"
            "HABILIDADES\n"
            "SQL, Power BI, Excel, Python, Tableau, dbt, MySQL, Looker"
        ),
    },
    {
        "full_name": "Victor Henrique Lopes",
        "email": "victor.lopes@email.com",
        "phone": "(91) 80012-3456",
        "cpf": "000.111.222-99",
        "location": "Belém, PA",
        "current_role": "Analista de Dados Pleno",
        "experience_years": 4,
        "education": "Bacharelado em Engenharia de Produção – UFPA",
        "skills": json.dumps(["Python", "SQL", "pandas", "scikit-learn", "Power BI",
                               "AWS", "Docker", "Airflow"]),
        "resume_filename": "victor_henrique_lopes.pdf",
        "resume_text": (
            "Victor Henrique Lopes — Analista de Dados Pleno\n"
            "Belém, PA | victor.lopes@email.com\n\n"
            "RESUMO\n"
            "4 anos em análise de dados com Python. Interesse crescente em IA generativa "
            "e LLMs para automação de relatórios.\n\n"
            "EXPERIÊNCIA\n"
            "Analista de Dados — LogTech PA (2022–atual)\n"
            "- Pipelines ETL com Python e Airflow\n"
            "- Dashboards Power BI para diretoria\n"
            "- Modelos ML com scikit-learn para otimização de rotas\n"
            "- Primeiros experimentos com API OpenAI para geração de relatórios\n\n"
            "FORMAÇÃO\n"
            "Bacharelado em Engenharia de Produção — UFPA (2020)\n\n"
            "HABILIDADES\n"
            "Python, SQL, pandas, scikit-learn, Power BI, AWS, Docker, Airflow"
        ),
    },
]

# ---------------------------------------------------------------------------
# Pre-calculated match scores [candidate_idx, job_idx, overall, skills, exp, edu, semantic, analysis]
# job_idx 0 = "Engenheiro de IA Pleno", job_idx 1 = "Desenvolvedor Backend Sênior"
# ---------------------------------------------------------------------------
_MATCHES = [
    # AI/ML engineers vs IA job (strong)
    (0, 0, 0.95, 0.95, 0.90, 0.95, 0.97, "Candidato altamente qualificado. Experiência direta com RAG, ChromaDB, FastAPI e LLMs. Mestrado relevante. Fortemente recomendado."),
    (1, 0, 0.92, 0.90, 0.88, 0.98, 0.93, "Doutora em NLP com publicações em embeddings para português. Expertise técnica excelente para a vaga."),
    (2, 0, 0.80, 0.78, 0.72, 0.75, 0.82, "Boa experiência prática com LLMs e FastAPI. 3 anos de experiência, abaixo do ideal de 3+. Candidato promissor."),
    (3, 0, 0.93, 0.91, 0.95, 0.92, 0.94, "Tech Lead com 6 anos e experiência direta em RAG, LLaMA e Kubernetes. Excelente candidata."),
    (4, 0, 0.88, 0.88, 0.85, 0.80, 0.90, "Especialista em LangChain e LangGraph. Experiência com APIs Anthropic. Muito bom fit técnico."),
    # Backend devs vs IA job (partial)
    (5, 0, 0.42, 0.35, 0.80, 0.70, 0.38, "Excelente em backend mas sem experiência direta em LLMs, RAG ou embeddings. Requer requalificação para a vaga de IA."),
    (6, 0, 0.38, 0.30, 0.65, 0.70, 0.35, "Background em Python e APIs, mas sem experiência em IA/ML. Não recomendado para esta vaga."),
    (7, 0, 0.30, 0.20, 0.70, 0.70, 0.28, "Node.js/TypeScript — stack diferente do requisitado. Sem experiência em IA. Não adequado."),
    (8, 0, 0.40, 0.35, 0.60, 0.65, 0.38, "Python e FastAPI sólidos, mas sem ML/IA. Poderia migrar com mentoria. Score baixo para esta vaga."),
    (9, 0, 0.45, 0.38, 0.90, 0.80, 0.42, "8 anos de experiência e Go, mas foco em sistemas distribuídos, não IA. Parcialmente adequado."),
    # Frontend devs vs IA job (fraco)
    (10, 0, 0.10, 0.05, 0.70, 0.65, 0.08, "Stack frontend (React/Next.js). Sem qualquer experiência em IA ou Python. Não adequado."),
    (11, 0, 0.08, 0.05, 0.55, 0.60, 0.07, "Desenvolvedor frontend. Não possui habilidades técnicas para esta vaga de IA."),
    (12, 0, 0.12, 0.05, 0.45, 0.70, 0.10, "Frontend com React/TypeScript. Sem experiência em IA. Não recomendado."),
    (13, 0, 0.10, 0.05, 0.65, 0.55, 0.08, "Frontend com Angular. Sem match técnico para a vaga de IA."),
    (14, 0, 0.08, 0.05, 0.55, 0.55, 0.07, "UI/Design. Sem habilidades técnicas de IA ou backend. Não adequado."),
    # Data analysts vs IA job (moderate)
    (15, 0, 0.62, 0.58, 0.72, 0.80, 0.60, "Forte em Python e scikit-learn. Sem experiência direta com LLMs/RAG, mas base sólida para transição."),
    (16, 0, 0.65, 0.60, 0.78, 0.75, 0.63, "Engenheira de dados com experiência em Python e LangChain básico. Potencial de desenvolvimento para a vaga."),
    (17, 0, 0.55, 0.50, 0.55, 0.85, 0.52, "Cientista de dados com PyTorch e interesse em LLMs. Mestrado em Estatística. Promissor mas inexperiente em produção com IA."),
    (18, 0, 0.18, 0.15, 0.60, 0.40, 0.15, "BI/SQL. Muito distante do perfil de IA/ML necessário."),
    (19, 0, 0.40, 0.35, 0.60, 0.55, 0.38, "Python e scikit-learn básicos. Interesse em LLMs mas sem experiência prática. Score insuficiente."),
    # AI/ML engineers vs Backend job (moderate-high)
    (0, 1, 0.72, 0.70, 0.85, 0.90, 0.68, "Forte em Python e FastAPI mas foco em IA. Adequado para o backend, mas pode estar overqualified em IA."),
    (1, 1, 0.60, 0.55, 0.80, 0.92, 0.58, "Pesquisadora. Python e FastAPI presentes, mas foco acadêmico em NLP, não backend enterprise."),
    (2, 1, 0.68, 0.65, 0.65, 0.72, 0.66, "FastAPI e Docker sólidos. Adequado para backend pleno, mas perfil mais voltado a IA."),
    (3, 1, 0.70, 0.68, 0.90, 0.85, 0.67, "Experiência sólida em APIs, Docker e AWS. Pode atuar no backend, mas especialização é IA."),
    (4, 1, 0.65, 0.62, 0.78, 0.75, 0.63, "LangChain e FastAPI. Adequado parcialmente, mas perfil de IA supera o requisito de backend puro."),
    # Backend devs vs Backend job (strong)
    (5, 1, 0.97, 0.95, 0.95, 0.85, 0.98, "Perfil ideal. 7 anos, Python + FastAPI + Kafka + Kubernetes. Tech Lead experiente. Fortemente recomendada."),
    (6, 1, 0.85, 0.82, 0.88, 0.82, 0.84, "Forte fit. Python/Django, PostgreSQL, Redis, CI/CD. 5 anos de experiência sólida."),
    (7, 1, 0.82, 0.78, 0.88, 0.80, 0.80, "Node.js/TypeScript com GraphQL e Kafka. Não é Python mas cobre os requisitos de backend enterprise."),
    (8, 1, 0.80, 0.78, 0.75, 0.75, 0.79, "Python/FastAPI com boas práticas. Sólido para posição pleno, pode crescer para sênior."),
    (9, 1, 0.93, 0.90, 0.98, 0.88, 0.92, "Principal Engineer com Go e Python. Sistemas distribuídos e liderança. Excelente candidata."),
    # Frontend devs vs Backend job (fraco)
    (10, 1, 0.20, 0.15, 0.72, 0.70, 0.18, "Frontend. Node.js presente mas sem experiência em backend APIs, bancos de dados ou cloud necessários."),
    (11, 1, 0.18, 0.12, 0.58, 0.65, 0.15, "Frontend React/Vue. Sem backend sólido. Não recomendado."),
    (12, 1, 0.15, 0.10, 0.48, 0.72, 0.13, "Next.js e TypeScript, mas foco em UI. Sem banco de dados ou infraestrutura. Não adequado."),
    (13, 1, 0.22, 0.15, 0.68, 0.58, 0.20, "React/Angular. Docker básico presente mas sem APIs backend ou bancos. Não recomendado."),
    (14, 1, 0.12, 0.08, 0.58, 0.55, 0.10, "UI/UX. Sem habilidades de backend. Não adequado."),
    # Data analysts vs Backend job (fraco-moderate)
    (15, 1, 0.52, 0.48, 0.75, 0.78, 0.50, "Python e SQL sólidos, AWS presente. Sem APIs backend mas base razoável."),
    (16, 1, 0.58, 0.55, 0.82, 0.75, 0.55, "Engenheira de dados com Python, Kafka e Docker. Pode migrar para backend com alguma requalificação."),
    (17, 1, 0.38, 0.32, 0.55, 0.82, 0.35, "Python e SQL mas foco em dados científicos, não APIs. Score insuficiente."),
    (18, 1, 0.22, 0.18, 0.60, 0.42, 0.20, "SQL e BI. Sem APIs ou infraestrutura. Não adequado."),
    (19, 1, 0.45, 0.40, 0.62, 0.58, 0.43, "Python e Airflow. Pode migrar para backend mas precisa de requalificação em APIs e testes."),
]

# ---------------------------------------------------------------------------
# Pipeline entries
# 10 triagem, 5 entrevista, 3 teste_tecnico, 1 aprovado, 1 rejeitado
# All against job_posting_id = 1 (IA job)
# ---------------------------------------------------------------------------
_PIPELINE_STAGES = [
    # stage, candidate_idx, notes
    ("triagem",       0,  "Excelente perfil. Aguardando confirmação de interesse."),
    ("triagem",       1,  "Doutora em NLP. Verificar disponibilidade."),
    ("triagem",       2,  "Bom perfil técnico. Avaliar experiência prática."),
    ("triagem",       3,  "Tech Lead com 6 anos. Verificar pretensão salarial."),
    ("triagem",       4,  "LangChain/LangGraph specialist. Excelente."),
    ("triagem",      15,  "Analista de dados com Python. Potencial para transição."),
    ("triagem",      16,  "Engenheira de dados. LangChain básico presente."),
    ("triagem",      17,  "Cientista de dados. PyTorch e interesse em LLMs."),
    ("triagem",       5,  "Backend forte. Sem IA mas pode ser treinado."),
    ("triagem",       9,  "Principal Engineer. Overqualified mas interesse declarado."),
    ("entrevista",    0,  "Primeira entrevista agendada — 2026-04-20."),
    ("entrevista",    3,  "Entrevista técnica marcada com tech lead."),
    ("entrevista",    1,  "Entrevista com equipe de pesquisa."),
    ("entrevista",    4,  "Entrevista agendada — validar fit cultural."),
    ("entrevista",   16,  "Entrevista exploratória sobre transição para IA."),
    ("teste_tecnico", 0,  "Teste de RAG pipeline enviado. Prazo: 5 dias."),
    ("teste_tecnico", 3,  "Desafio técnico: implementar sistema de Q&A com ChromaDB."),
    ("teste_tecnico", 1,  "Teste de embeddings e avaliação de reranker."),
    ("aprovado",      3,  "Aprovada! Proposta enviada em 2026-04-10. Aguardando resposta."),
    ("rejeitado",     7,  "Stack incompatível (Node.js). Encaminhado para vaga de backend."),
]


def seed_database() -> None:
    """Insert sample recruitment data. Idempotent — skips if candidates already exist."""
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        if count > 0:
            return  # Already seeded

        now = _TODAY.isoformat()

        # Insert job postings
        for i, job in enumerate(_JOB_POSTINGS):
            conn.execute(
                """INSERT INTO job_postings
                   (title, company, description, requirements, desired_skills,
                    seniority_level, work_model, salary_range, created_by, created_at, is_active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (job["title"], job["company"], job["description"], job["requirements"],
                 job["desired_skills"], job["seniority_level"], job["work_model"],
                 job["salary_range"], 1, _d(30 - i * 5), True),
            )

        job_ids = [row[0] for row in conn.execute("SELECT id FROM job_postings ORDER BY id")]

        # Insert candidates
        for i, c in enumerate(_CANDIDATES):
            conn.execute(
                """INSERT INTO candidates
                   (full_name, email, phone, cpf, location, current_role,
                    experience_years, education, skills, resume_filename,
                    resume_text, created_at, is_active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (c["full_name"], c["email"], c["phone"], c["cpf"], c["location"],
                 c["current_role"], c["experience_years"], c["education"], c["skills"],
                 c["resume_filename"], c["resume_text"], _d(20 - i), True),
            )

        cand_ids = [row[0] for row in conn.execute("SELECT id FROM candidates ORDER BY id")]

        # Insert match scores
        for cand_idx, job_idx, overall, skills, exp, edu, semantic, analysis in _MATCHES:
            conn.execute(
                """INSERT INTO matches
                   (candidate_id, job_posting_id, overall_score, skills_score,
                    experience_score, education_score, semantic_score, analysis, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (cand_ids[cand_idx], job_ids[job_idx], overall, skills, exp, edu,
                 semantic, analysis, _d(15)),
            )

        # Insert pipeline entries
        for stage, cand_idx, notes in _PIPELINE_STAGES:
            conn.execute(
                """INSERT INTO pipeline
                   (candidate_id, job_posting_id, stage, notes, updated_by, updated_at)
                   VALUES (?,?,?,?,?,?)""",
                (cand_ids[cand_idx], job_ids[0], stage, notes, 1, now),
            )


def seed_users() -> None:
    """Seed analyst + manager users if table is empty."""
    from src.api.auth import hash_password
    from datetime import timezone
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO users (username, password_hash, full_name, role, created_at) VALUES (?,?,?,?,?)",
            [
                ("analyst", hash_password("analyst123"), "Ana Recrutadora",       "analyst", now),
                ("manager", hash_password("manager123"), "Marcos Gestor de RH",   "manager", now),
            ],
        )
    print("=" * 60)
    print("  DEFAULT USERS: analyst/analyst123, manager/manager123")
    print("=" * 60)


def init_db() -> None:
    """Create tables and seed if the DB file does not yet contain data."""
    create_tables()
    seed_users()
    seed_database()


if __name__ == "__main__":
    init_db()
    with get_db() as conn:
        cand_count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        job_count = conn.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0]
        match_count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        pipeline_count = conn.execute("SELECT COUNT(*) FROM pipeline").fetchone()[0]
    print(f"Seeded {cand_count} candidates, {job_count} job postings, "
          f"{match_count} matches, {pipeline_count} pipeline entries.")
