#!/usr/bin/env python3
"""Generate JoJo-themed Markdown test notes for Echos / Obsidian indexing."""

from __future__ import annotations

import textwrap
from pathlib import Path

BASE = Path("/Users/aayush/Documents/obsidian/great-days")

# (folder_name, part_num, part_title, [(slug, display_name, stand_or_power_slug, stand_title, blurb), ...])
PARTS: list[tuple[str, int, str, list[tuple[str, str, str, str, str]]]] = [
    (
        "Part-01-Phantom-Blood",
        1,
        "Phantom Blood",
        [
            ("Jonathan-Joestar", "Jonathan Joestar", "Hamon-Ripple", "Hamon (Ripple)", "The noble first JoJo; trains under Zeppeli to master the Ripple."),
            ("Dio-Brando", "Dio Brando", "Vampire-Powers", "Vampire / rejection of humanity", "Rival turned immortal villain; iconic mask and ambition."),
            ("Robert-EO-Speedwagon", "Robert E. O. Speedwagon", "No-Stand-Speedwagon", "Street smarts & heart of gold", "Founding ally; later the Speedwagon Foundation."),
            ("Will-Zeppeli", "Will Anthonio Zeppeli", "Hamon-Zeppeli", "Hamon (Ripple)", "Baron Zeppeli teaches Jonathan the way of the Ripple."),
            ("Erina-Pendleton", "Erina Pendleton", "No-Stand-Erina", "No supernatural ability", "Jonathan's beloved; moral anchor of Part 1."),
            ("George-Joestar-I", "George Joestar I", "No-Stand-George", "No supernatural ability", "Jonathan's father; kindness shapes the Joestar line."),
            ("Bruford", "Bruford", "Dark-Knight-Bruford", "Dark Knight Sword", "Zombie knight with honor; memorable early foe."),
            ("Tarkus", "Tarkus", "Dark-Knight-Tarkus", "Brute strength", "Towering zombie warrior; tests Jonathan's resolve."),
            ("Wang-Chan", "Wang Chan", "No-Stand-Wang", "Zombie servitude", "Dio's henchman; ties Part 1 to later plots."),
            ("Dire", "Dire", "Hamon-Dire", "Hamon (Ripple)", "Zeppeli's student; Thunder Cross Split Attack."),
        ],
    ),
    (
        "Part-02-Battle-Tendency",
        2,
        "Battle Tendency",
        [
            ("Joseph-Joestar", "Joseph Joestar", "Hamon-Joseph", "Hamon (Ripple)", "Trickster JoJo; faces the Pillar Men with wit."),
            ("Caesar-Zeppeli", "Caesar Anthonio Zeppeli", "Hamon-Caesar", "Hamon (Ripple)", "Bubble-launching Ripple warrior; Zeppeli legacy."),
            ("Lisa-Lisa", "Lisa Lisa", "Hamon-Lisa-Lisa", "Hamon (Ripple)", "Elite Ripple master; Joseph's teacher."),
            ("Kars", "Kars", "Ultimate-Lifeform", "Ultimate Life Form", "Pillar Men leader; seeks perfection above the sun."),
            ("Esidisi", "Esidisi", "Heat-Mode", "Heat Mode / blood vessels", "Emotional Pillar Man; boiling blood tactics."),
            ("Wamuu", "Wamuu", "Wind-Mode", "Wind Mode / Divine Sandstorm", "Honorable warrior of the wind."),
            ("Santana", "Santana", "Pillar-Santana", "Pillar Man physiology", "First Pillar Man uncovered; shape-shifting horror."),
            ("Rudol-von-Stroheim", "Rudol von Stroheim", "Cyborg-Stroheim", "German science / cyborg", "Bizarre ally; SCIENCE and resolve."),
            ("Suzi-Q", "Suzi Q", "No-Stand-Suzi", "No supernatural ability", "Joseph's future wife; warmth and comedy."),
            ("Smokey-Brown", "Smokey Brown", "No-Stand-Smokey", "No supernatural ability", "Young friend in New York; witnesses Joseph's heart."),
        ],
    ),
    (
        "Part-03-Stardust-Crusaders",
        3,
        "Stardust Crusaders",
        [
            ("Jotaro-Kujo", "Jotaro Kujo", "Star-Platinum", "Star Platinum", "Stoic high-schooler; ORA ORA and time stop."),
            ("Joseph-Joestar-3", "Joseph Joestar", "Hermit-Purple", "Hermit Purple", "Older Joseph; spirit photography Stand."),
            ("Muhammad-Avdol", "Muhammad Avdol", "Magicians-Red", "Magician's Red", "Fire fortune-teller; loyal strategist."),
            ("Noriaki-Kakyoin", "Noriaki Kakyoin", "Hierophant-Green", "Hierophant Green", "Cherry-loving tactician; Emerald Splash."),
            ("Jean-Pierre-Polnareff", "Jean Pierre Polnareff", "Silver-Chariot", "Silver Chariot", "French swordsman; quest for justice."),
            ("Iggy", "Iggy", "The-Fool", "The Fool", "Boston terrier with sand Stand; reluctant hero."),
            ("DIO-Brando-3", "Dio Brando", "The-World", "The World", "Time-stopping apex villain; WRYYYY."),
            ("Hol-Horse", "Hol Horse", "Emperor", "Emperor", "Gun Stand cowboy; Emperor's bullets."),
            ("Vanilla-Ice", "Vanilla Ice", "Cream", "Cream", "Devoted servant; void sphere devours space."),
            ("Daniel-J-DArby", "Daniel J. D'Arby", "Osiris", "Osiris", "Gambler who steals souls; tense mind games."),
        ],
    ),
    (
        "Part-04-Diamond-is-Unbreakable",
        4,
        "Diamond is Unbreakable",
        [
            ("Josuke-Higashikata-4", "Josuke Higashikata", "Crazy-Diamond", "Crazy Diamond", "Morioh delinquent with healing restoration."),
            ("Koichi-Hirose", "Koichi Hirose", "Echoes", "Echoes (Acts 1–3)", "Growth arc from timid to reliable."),
            ("Okuyasu-Nijimura", "Okuyasu Nijimura", "The-Hand", "The Hand", "Erasure space; big heart, simple goals."),
            ("Rohan-Kishibe", "Rohan Kishibe", "Heavens-Door", "Heaven's Door", "Manga artist; reads people like pages."),
            ("Jotaro-Kujo-4", "Jotaro Kujo", "Star-Platinum-4", "Star Platinum", "Marine biologist mentor in Morioh."),
            ("Yoshikage-Kira", "Yoshikage Kira", "Killer-Queen", "Killer Queen", "Quiet killer seeking a peaceful life."),
            ("Reimi-Sugimoto", "Reimi Sugimoto", "Ghost-Reimi", "Ghost / guiding spirit", "Victim who guides the heroes."),
            ("Tonio-Trussardi", "Tonio Trussardi", "Pearl-Jam", "Pearl Jam", "Chef Stand; bizarrely healing cuisine."),
            ("Yukako-Yamagishi", "Yukako Yamagishi", "Love-Deluxe", "Love Deluxe", "Hair Stand; intense devotion to Koichi."),
            ("Hayato-Kawajiri", "Hayato Kawajiri", "No-Stand-Hayato", "No Stand", "Child detective; courage against Kira."),
        ],
    ),
    (
        "Part-05-Golden-Wind",
        5,
        "Golden Wind (Vento Aureo)",
        [
            ("Giorno-Giovanna", "Giorno Giovanna", "Gold-Experience", "Gold Experience / GER", "Dream of becoming a Gang-Star."),
            ("Bruno-Bucciarati", "Bruno Bucciarati", "Sticky-Fingers", "Sticky Fingers", "Zipper portals; protective capo."),
            ("Leone-Abbacchio", "Leone Abbacchio", "Moody-Blues", "Moody Blues", "Replay investigator; haunted past."),
            ("Guido-Mista", "Guido Mista", "Sex-Pistols", "Sex Pistols", "Four (sometimes five) bullet riders."),
            ("Narancia-Ghirga", "Narancia Ghirga", "Aerosmith", "Aerosmith", "Radar and bombs; loyal to Bruno."),
            ("Pannacotta-Fugo", "Pannacotta Fugo", "Purple-Haze", "Purple Haze", "Deadly virus cloud; brilliant temper."),
            ("Trish-Una", "Trish Una", "Spice-Girl", "Spice Girl", "Softens matter; daughter of the boss."),
            ("Diavolo", "Diavolo (The Boss)", "King-Crimson", "King Crimson", "Time erase; split identity with Doppio."),
            ("Vinegar-Doppio", "Vinegar Doppio", "King-Crimson-Doppio", "King Crimson (shared)", "Innocent-seeming alter of Diavolo."),
            ("Risotto-Nero", "Risotto Nero", "Metallica", "Metallica", "Iron manipulation in blood; La Squadra."),
        ],
    ),
    (
        "Part-06-Stone-Ocean",
        6,
        "Stone Ocean",
        [
            ("Jolyne-Cujoh", "Jolyne Cujoh", "Stone-Free", "Stone Free", "String Stand; JoJo grit in Green Dolphin."),
            ("Ermes-Costello", "Ermes Costello", "Kiss", "Kiss", "Sticker duplicates; sister's revenge."),
            ("Foo-Fighters", "Foo Fighters", "Foo-Fighters-Stand", "Foo Fighters", "Plankton collective; fast learner."),
            ("Emporio-Alnino", "Emporio Alnino", "Burning-Down-House", "Burning Down the House", "Child hidden in the prison."),
            ("Narciso-Anasui", "Narciso Anasui", "Diver-Down", "Diver Down", "Phase through objects; redesigns internals."),
            ("Weather-Report", "Weather Report", "Weather-Report-Stand", "Weather Report / Heavy Weather", "Atmosphere control; tragic memory."),
            ("Jotaro-Kujo-6", "Jotaro Kujo", "Star-Platinum-6", "Star Platinum", "Disk-stolen father; stakes skyrocket."),
            ("Enrico-Pucci", "Enrico Pucci", "Whitesnake", "Whitesnake / C-Moon / Made in Heaven", "Dio's disciple; accelerates the universe."),
            ("Johngalli-A", "Johngalli A.", "Manhattan-Transfer", "Manhattan Transfer", "Sniping redirection Stand."),
            ("Lang-Rangler", "Lang Rangler", "Jumpin-Jack-Flash", "Jumpin' Jack Flash", "Zero-gravity microgravity horror."),
        ],
    ),
    (
        "Part-07-Steel-Ball-Run",
        7,
        "Steel Ball Run",
        [
            ("Johnny-Joestar", "Johnny Joestar", "Tusk", "Tusk (Acts 1–4)", "Spin and the infinite rotation."),
            ("Gyro-Zeppeli", "Gyro Zeppeli", "Ball-Breaker", "Ball Breaker / Steel Ball", "Executioner seeking innocence; Spin master."),
            ("Diego-Brando", "Diego Brando", "Scary-Monsters", "Scary Monsters / THE WORLD", "Raptor rival; parallel Dio."),
            ("Hot-Pants", "Hot Pants", "Cream-Starter", "Cream Starter", "Flesh spray healing; Vatican agent."),
            ("Mountain-Tim", "Mountain Tim", "Oh-Lonesome-Me", "Oh! Lonesome Me", "Rope body from Stand; cowboy."),
            ("Sandman", "Sandman", "In-a-Silent-Way", "In a Silent Way", "Sound-to-image sand traps."),
            ("Funny-Valentine", "Funny Valentine", "D4C", "Dirty Deeds Done Dirt Cheap", "Patriotism as multiverse traversal."),
            ("Lucy-Steel", "Lucy Steel", "Ticket-to-Ride", "Ticket to Ride", "Saint corpse convergence; key to victory."),
            ("Steven-Steel", "Steven Steel", "No-Stand-Steven", "No Stand", "Race promoter; Lucy's husband."),
            ("Ringo-Roadagain", "Ringo Roadagain", "Mandom", "Mandom", "Six-second rewind duelist."),
        ],
    ),
    (
        "Part-08-JoJolion",
        8,
        "JoJolion",
        [
            ("Josuke-Higashikata-8", "Josuke Higashikata (Josuke 8)", "Soft-and-Wet", "Soft & Wet", "Fusion mystery; bubbles steal properties."),
            ("Yasuho-Hirose", "Yasuho Hirose", "Paisley-Park", "Paisley Park", "GPS-like guidance through data."),
            ("Joshu-Higashikata", "Joshu Higashikata", "Nut-King-Call", "Nut King Call", "Nuts and bolts; comic relief and danger."),
            ("Norisuke-Higashikata-IV", "Norisuke Higashikata IV", "King-Nothing", "King Nothing", "Scent puzzle tracking."),
            ("Jobin-Higashikata", "Jobin Higashikata", "Speed-King", "Speed King", "Heat spots; ambition for the family."),
            ("Rai-Mamezuku", "Rai Mamezuku", "Doggy-Style", "Doggy Style", "Wire-like body; plant appraiser."),
            ("Poor-Tom", "Poor Tom", "Ozon-Baby", "Ozon Baby", "Pressure Stand; suburban trap."),
            ("Toru", "Toru", "Wonder-of-U", "Wonder of U", "Calamity pursues those who pursue."),
            ("Mitsuba-Higashikata", "Mitsuba Higashikata", "Awaking-III-Leaves", "Awaking III Leaves", "Vector redirection of harm."),
            ("Wu-Tomoki", "Dr. Wu Tomoki", "Doctor-Wu", "Doctor Wu", "Rock insect medicine; dust infiltration."),
        ],
    ),
    (
        "Part-09-The-JOJOLands",
        9,
        "The JOJOLands",
        [
            ("Jodio-Joestar", "Jodio Joestar", "November-Rain", "November Rain", "Rain that pins targets; modern Hawaii JoJo."),
            ("Dragona-Joestar", "Dragona Joestar", "Smooth-Operators", "Smooth Operators", "Skin-smoothing Stand; sibling heist crew."),
            ("Paco-Laburantes", "Paco Laburantes", "The-Hustle", "The Hustle", "Elastic muscle theft; bruiser energy."),
            ("Usagi-Alohaoe", "Usagi Alohaoe", "The-Matte-Kudasai", "The Matte Kudasai", "Duplication tricks; chaotic ally."),
            ("Rohan-Kishibe-9", "Rohan Kishibe", "Heavens-Door-9", "Heaven's Door", "Millionaire mangaka vacation; reads souls."),
            ("Charming-Man", "Charming Man", "Bigmouth-Strikes-Again", "Bigmouth Strikes Again", "Mud and terrain control; rival-turned-ally."),
            ("Meryl-Mei-Qi", "Meryl Mei Qi", "No-Stand-Meryl", "No Stand revealed (yet)", "Scholar of lava rocks; plot catalyst."),
            ("Barbara-Ann-Joestar", "Barbara Ann Joestar", "No-Stand-Barbara", "No Stand", "Family anchor in the islands."),
            ("Keila-Kang", "Keila Kang", "No-Stand-Keila", "No Stand (support)", "Local contact; grounds the crew in Hawaii."),
            ("Leo", "Leo", "No-Stand-Leo", "No Stand", "Crew associate; test note for minor roles."),
        ],
    ),
]


def char_md(
    part_num: int,
    part_title: str,
    folder: str,
    slug: str,
    name: str,
    stand_slug: str,
    stand_title: str,
    blurb: str,
) -> str:
    stand_file = f"{slug}-Stand.md"
    return textwrap.dedent(
        f"""\
        ---
        type: character
        part: {part_num}
        part_name: "{part_title}"
        stand: "[[{stand_file.replace('.md', '')}]]"
        universe: jojo-bizarre-adventure
        tags: [jojo, part-{part_num:02d}, character, great-days-test]
        ---

        # {name}

        {blurb}

        **Part:** [[{folder}/README|Part {part_num}: {part_title}]]  
        **Ability / Stand notes:** [[{stand_file.replace('.md', '')}]]

        Related universe index: [[README|Great Days test vault]]
        """
    ).strip()


def stand_md(
    part_num: int,
    part_title: str,
    folder: str,
    slug: str,
    name: str,
    stand_slug: str,
    stand_title: str,
    blurb: str,
) -> str:
    char_file = f"{slug}.md"
    return textwrap.dedent(
        f"""\
        ---
        type: stand
        part: {part_num}
        part_name: "{part_title}"
        user: "[[{slug}]]"
        stand_name: "{stand_title}"
        universe: jojo-bizarre-adventure
        tags: [jojo, part-{part_num:02d}, stand, great-days-test]
        ---

        # {stand_title}

        Used by **[[{slug}]]** ({name}).

        _Summary:_ {blurb}

        **Part:** [[{folder}/README|Part {part_num}: {part_title}]]  
        Back to character: [[{slug}]]

        See also: [[README|Great Days test vault]]
        """
    ).strip()


def readme_part(part_num: int, part_title: str, folder: str, entries: list) -> str:
    lines = [
        "---",
        f'type: part-index',
        f"part: {part_num}",
        f'part_name: "{part_title}"',
        "tags: [jojo, part-index, great-days-test]",
        "---",
        "",
        f"# Part {part_num}: {part_title}",
        "",
        "Top characters (test data for Echos indexing):",
        "",
    ]
    for slug, name, _, stand_title, _ in entries:
        lines.append(f"- [[{slug}]] — *{stand_title}*")
    lines.append("")
    lines.append("[[README|← Vault home]]")
    return "\n".join(lines)


def readme_root() -> str:
    return textwrap.dedent(
        """\
        ---
        type: vault-index
        title: "Great Days — JoJo test corpus"
        purpose: "Synthetic notes for Echos vault indexing / embedding tests"
        tags: [jojo, index, great-days-test]
        ---

        # Great Days (test vault)

        This vault contains **10 characters × 9 parts** of *JoJo's Bizarre Adventure*,
        each with a **character** note and a **stand / power** note, plus per-part indexes.

        ## Parts

        - [[Part-01-Phantom-Blood/README|Part 1 — Phantom Blood]]
        - [[Part-02-Battle-Tendency/README|Part 2 — Battle Tendency]]
        - [[Part-03-Stardust-Crusaders/README|Part 3 — Stardust Crusaders]]
        - [[Part-04-Diamond-is-Unbreakable/README|Part 4 — Diamond is Unbreakable]]
        - [[Part-05-Golden-Wind/README|Part 5 — Golden Wind]]
        - [[Part-06-Stone-Ocean/README|Part 6 — Stone Ocean]]
        - [[Part-07-Steel-Ball-Run/README|Part 7 — Steel Ball Run]]
        - [[Part-08-JoJolion/README|Part 8 — JoJolion]]
        - [[Part-09-The-JOJOLands/README|Part 9 — The JOJOLands]]

        Cross-part links for testing: [[Part-03-Stardust-Crusaders/DIO-Brando-3|Dio Part 3]] · [[Part-01-Phantom-Blood/Dio-Brando|Dio Part 1]]
        """
    ).strip()


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / "README.md").write_text(readme_root(), encoding="utf-8")

    total_chars = 0
    for folder, part_num, part_title, entries in PARTS:
        d = BASE / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / "README.md").write_text(readme_part(part_num, part_title, folder, entries), encoding="utf-8")

        for slug, name, stand_slug, stand_title, blurb in entries:
            (d / f"{slug}.md").write_text(
                char_md(part_num, part_title, folder, slug, name, stand_slug, stand_title, blurb),
                encoding="utf-8",
            )
            (d / f"{slug}-Stand.md").write_text(
                stand_md(part_num, part_title, folder, slug, name, stand_slug, stand_title, blurb),
                encoding="utf-8",
            )
            total_chars += 1

    print(f"Wrote {BASE}")
    print(f"Parts: {len(PARTS)}, characters: {total_chars}, md files: {total_chars * 2 + len(PARTS) + 1} (approx)")


if __name__ == "__main__":
    main()
