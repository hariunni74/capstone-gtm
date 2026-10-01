from .models import ResearchBrief


def build_brief(topic: str, geography: str, target_customer: str) -> ResearchBrief:
    topic = topic.strip()
    geography = geography.strip()
    target_customer = target_customer.strip()

    questions = [
        f"What is the size and recent direction of the market for {topic} in {geography}?",
        f"Who are the main customer segments for {topic} in {geography}?",
        f"What problems does {target_customer} face that this product could solve?",
        f"Who are the leading direct and indirect competitors in {geography}?",
        "What features and positioning distinguish the competitors?",
        "What public pricing or commercial models do competitors offer?",
        f"Which channels could reach {target_customer} effectively?",
        f"What regulatory or adoption constraints matter in {geography}?",
    ]

    return ResearchBrief(
        topic=topic,
        geography=geography,
        target_customer=target_customer,
        questions=questions,
    )