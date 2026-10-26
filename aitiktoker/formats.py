from dataclasses import dataclass


@dataclass(frozen=True)
class ComedyFormat:
    id: str
    name: str
    instructions: str


FORMATS = {
    f.id: f
    for f in [
        ComedyFormat(
            "self_review",
            "Product reviews itself",
            "The product speaks in first person with a dramatic, slightly unhinged personality. "
            "It brags about its real features and roasts the viewer's life without it.",
        ),
        ComedyFormat(
            "red_flag",
            "Red flag / green flag",
            "Rate the product like someone you're dating. List green flags (real features) and one "
            "honest, funny 'red flag' taken from the brief's notes or limitations.",
        ),
        ComedyFormat(
            "villain_origin",
            "Villain origin story",
            "A dramatic movie-trailer narrator tells how life before this product was a tragedy, "
            "then the product arrives as the hero. Over-the-top drama, everyday problem.",
        ),
        ComedyFormat(
            "group_chat",
            "Group chat drama",
            "Write the scenes as messages in a group chat between the product and the viewer's "
            "other belongings, who are jealous of it. Each scene is one or two chat messages.",
        ),
        ComedyFormat(
            "genalpha_translator",
            "Gen Alpha translator",
            "First describe the product in heavy Thai Gen Z/Gen Alpha slang, then a 'translation for "
            "millennials' in plain Thai. Alternate slang and translation scenes.",
        ),
        ComedyFormat(
            "sports_commentator",
            "Sports commentator",
            "A hyped Thai football commentator narrates someone using the product as if it were the "
            "final minute of a match.",
        ),
        ComedyFormat(
            "npc_vs_main",
            "NPC vs main character",
            "Contrast an 'NPC' life without the product (boring, repetitive) with a 'main character' "
            "life with it. Alternate NPC and main-character scenes.",
        ),
    ]
}
