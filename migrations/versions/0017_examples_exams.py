"""example sentences for the «Экзамены» group (AWL + IELTS trends)

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-22

Content upgrade batch 1: these 100 academic/IELTS words had no example sentence
(0% coverage), and academic vocabulary is exactly where a usage example does the
most work. Hand-authored, level-appropriate. Idempotent: only fills words whose
example is still NULL; downgrade clears only the exact examples it set.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


EXAMPLES: dict[str, str] = {
    # academic_awl
    "analyze": "Researchers analyze the data to find patterns.",
    "approach": "We need a new approach to solve this problem.",
    "aspect": "Cost is just one aspect of the decision.",
    "category": "These books fall into the same category.",
    "concept": "The concept of time is hard to define.",
    "context": "A word's meaning depends on the context.",
    "criteria": "The project met all the selection criteria.",
    "data": "The data show a clear upward trend.",
    "environment": "Plastic waste harms the environment.",
    "establish": "The company was established in 1990.",
    "identify": "Scientists identified three main causes.",
    "interpret": "It is hard to interpret these results.",
    "policy": "The government introduced a new health policy.",
    "principle": "Equality is a basic principle of democracy.",
    "region": "This region is famous for its wine.",
    "require": "This job requires a lot of patience.",
    "research": "Her research focuses on climate change.",
    "respond": "How did they respond to the news?",
    "section": "Read the next section of the report.",
    "sector": "He works in the public sector.",
    "significant": "There was a significant rise in prices.",
    "theory": "Einstein's theory changed physics.",
    "vary": "Prices vary from shop to shop.",
    "achieve": "She achieved her goal after years of work.",
    "acquire": "He acquired fluent English while living abroad.",
    "assist": "Volunteers assist the elderly every week.",
    "authority": "Local authorities approved the new plan.",
    "consist": "The team consists of five members.",
    "constitute": "Women constitute half of the workforce.",
    "contribute": "Everyone contributed to the project's success.",
    "coordinate": "She coordinates the marketing team.",
    "demonstrate": "The study demonstrates a clear link.",
    "dominate": "One company dominates the market.",
    "emphasis": "The course puts emphasis on speaking.",
    "focus": "Let's focus on the main issue.",
    "implement": "The school implemented a new system.",
    "imply": "His silence seemed to imply agreement.",
    "initial": "My initial reaction was surprise.",
    "instance": "There were several instances of error.",
    "invest": "They invested heavily in new technology.",
    "maintain": "It is important to maintain good habits.",
    "minimize": "We tried to minimize the risks.",
    "objective": "The main objective is to cut costs.",
    "obtain": "You can obtain a visa online.",
    "occupy": "The meeting occupied the whole morning.",
    "option": "Quitting was not an option.",
    "participate": "Students participate in weekly debates.",
    "perceive": "People perceive the brand as reliable.",
    "potential": "She has great potential as a leader.",
    "primary": "The primary cause was human error.",
    "prior": "No prior experience is required.",
    "procedure": "Follow the safety procedure carefully.",
    "promote": "The campaign promotes healthy eating.",
    "proportion": "A large proportion of students passed.",
    "publish": "The journal publishes new research monthly.",
    "regulate": "Laws regulate how banks operate.",
    "relevant": "Please include only relevant details.",
    "restrict": "The rules restrict access to the area.",
    "reveal": "The survey revealed surprising results.",
    "sequence": "Follow the steps in the right sequence.",
    "shift": "There has been a shift in public opinion.",
    "strategy": "The company changed its marketing strategy.",
    "sufficient": "We do not have sufficient evidence.",
    "summary": "Write a short summary of the article.",
    "survey": "The survey covered a thousand people.",
    "sustain": "It is hard to sustain such fast growth.",
    "technique": "She learned a new painting technique.",
    "transfer": "He transferred to another department.",
    "transform": "The internet transformed how we work.",
    "trend": "There is a growing trend toward remote work.",
    "ultimate": "Their ultimate goal is world peace.",
    "undertake": "The firm undertook a major project.",
    "utilize": "We should utilize our resources better.",
    "version": "This is the latest version of the app.",
    "via": "We flew to Rome via Paris.",
    "volume": "The volume of sales doubled this year.",
    "welfare": "The state cares for the welfare of children.",
    # ielts_trends
    "increase": "Sales increased sharply in 2020.",
    "decrease": "The number of visitors decreased last year.",
    "rise": "House prices continued to rise.",
    "decline": "Birth rates declined over the decade.",
    "drop": "Temperatures dropped suddenly at night.",
    "fluctuate": "Prices fluctuated throughout the year.",
    "peak": "Demand reached its peak in summer.",
    "plateau": "Sales rose and then reached a plateau.",
    "soar": "Profits soared after the new launch.",
    "plummet": "Stock prices plummeted overnight.",
    "surge": "There was a surge in online shopping.",
    "dip": "Sales saw a slight dip in March.",
    "steady": "The economy showed steady growth.",
    "gradual": "There was a gradual rise in income.",
    "sharp": "The chart shows a sharp increase.",
    "dramatic": "There was a dramatic fall in sales.",
    "slight": "Prices showed only a slight change.",
    "substantial": "The company made a substantial profit.",
    "approximately": "Approximately 40% of people agreed.",
    "respectively": "Sales were 20 and 30 units respectively.",
    "whereas": "Exports rose, whereas imports fell.",
    "figure": "The figure rose to five million.",
    "amount": "A large amount of money was spent.",
}


def upgrade() -> None:
    conn = op.get_bind()
    stmt = sa.text(
        "UPDATE words SET example_sentence = :e "
        "WHERE track = 'en' AND normalized_word = :n AND example_sentence IS NULL"
    )
    for normalized, example in EXAMPLES.items():
        conn.execute(stmt, {"e": example, "n": normalized})


def downgrade() -> None:
    conn = op.get_bind()
    stmt = sa.text(
        "UPDATE words SET example_sentence = NULL "
        "WHERE track = 'en' AND normalized_word = :n AND example_sentence = :e"
    )
    for normalized, example in EXAMPLES.items():
        conn.execute(stmt, {"e": example, "n": normalized})
