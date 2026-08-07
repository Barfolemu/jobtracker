from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

DEFAULT_MODEL = "gpt-4o-mini"


class JobExtraction(BaseModel):
    company_name: str = Field(description="Hiring company name, or 'Unknown' if not determinable")
    role_title: str = Field(description="Job title/role, or 'Unknown' if not determinable")
    confidence: float = Field(description="0-1 confidence that both fields above are correct")


_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You extract the company name and job title from a job-alert email. "
            "Give your best guess even if the email is ambiguous, and reflect your "
            "certainty in the confidence score rather than refusing to answer.",
        ),
        ("human", "Subject: {subject}\n\nBody:\n{body}"),
    ]
)


def build_extraction_chain(model: str = DEFAULT_MODEL):
    llm = ChatOpenAI(model=model, temperature=0)
    return _PROMPT | llm.with_structured_output(JobExtraction)


def extract(chain, subject: str, body: str) -> JobExtraction:
    return chain.invoke({"subject": subject, "body": body[:4000]})
