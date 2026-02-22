"""
Genre taxonomy for KNOB Radio.

Defines the canonical genre hierarchy and all mapping tables for normalizing
ID3 tags, directory names, and Discogs/MAEST labels into our taxonomy.
"""

# ── Canonical taxonomy ──────────────────────────────────────────────────────

TAXONOMY = {
    "Bass": [
        "Dubstep", "Deep Dubstep", "Riddim", "Grime", "Garage",
        "Drum & Bass", "Leftfield Bass", "Freeform Bass",
    ],
    "Electronic": [
        "House", "Deep House", "Progressive House", "Trance",
        "IDM", "Breakbeat", "Big Beat", "Glitch Hop",
    ],
    "Chill": [
        "Downtempo", "Chillout", "Lofi", "Ambient", "Trip Hop", "Chillstep",
    ],
    "Hip-Hop": ["Hip-Hop", "Trap", "Beats"],
    "Dub/Reggae": ["Dub", "Reggae"],
    "Metal": [
        "Heavy Metal", "Death Metal", "Black Metal", "Doom",
        "Thrash", "Stoner/Sludge",
    ],
    "Punk": ["Punk", "Hardcore", "Post-Punk", "Crust", "Skate Punk"],
    "Blues/Soul": ["Blues", "R&B", "Soul", "Funk"],
    "Jazz": ["Bebop", "Cool Jazz", "Free Jazz", "Fusion", "Latin Jazz", "Swing"],
    "Classical": ["Orchestral", "Chamber", "Solo", "Opera", "Modern/Contemporary"],
    "Pop/Rock": ["Pop", "Rock", "Indie", "Country", "Folk"],
}

# Build reverse lookup: subgenre -> parent
SUB_TO_PARENT = {}
for parent, subs in TAXONOMY.items():
    for sub in subs:
        SUB_TO_PARENT[sub] = parent

# All valid parent genres
VALID_PARENTS = set(TAXONOMY.keys())

# All valid subgenres
VALID_SUBS = set(SUB_TO_PARENT.keys())


# ── Content type directories ────────────────────────────────────────────────
# Directories whose contents are non-music (excluded from genre classification)

CONTENT_TYPE_DIRS = {
    "callsigns":     "callsign",
    "commercials":   "commercial",
    "promos":        "promo",
    "talking_clips": "talking",
    "SHOWS":         "talking",
    "abnormal":      "promo",    # station IDs / weird clips
}


# ── TAG_NORMALIZE ───────────────────────────────────────────────────────────
# Maps every observed ID3 genre string to (parent, sub).
# All 65 genre strings from the collection are covered.

TAG_NORMALIZE = {
    # Dubstep variants
    "Dubstep":                       ("Bass", "Dubstep"),
    "DubStep":                       ("Bass", "Dubstep"),
    "dubstep":                       ("Bass", "Dubstep"),
    "Deep Dubstep":                  ("Bass", "Deep Dubstep"),
    "Deep dubstep":                  ("Bass", "Deep Dubstep"),
    "Vocal Deep Dubstep":            ("Bass", "Deep Dubstep"),
    "DafuQ! [Dubstep]":              ("Bass", "Dubstep"),
    "Dirty/Heavy Dubstep/Grime":     ("Bass", "Dubstep"),
    "Dirty/heavy Dubstep/grime":     ("Bass", "Dubstep"),
    "Heavy Dubstep/Grime":           ("Bass", "Dubstep"),
    "Ambient Dubstep":               ("Chill", "Chillstep"),
    "LoveStep":                      ("Bass", "Dubstep"),
    "Dubstep,dub":                   ("Bass", "Dubstep"),

    # Dubstep / combo tags
    "Dubstep/Grime":                 ("Bass", "Grime"),
    "Dubstep / Grime / Funky":       ("Bass", "Grime"),
    "Dubstep / Riddim":              ("Bass", "Riddim"),
    "Dubstep / Trap":                ("Hip-Hop", "Trap"),
    "Dubstep / 2step ":              ("Bass", "Garage"),
    "Dubstep / 2step":               ("Bass", "Garage"),

    # Garage
    "FutureGarage":                  ("Bass", "Garage"),
    "Garage / Bassline / Grime":     ("Bass", "Garage"),
    "Deep Dubstep, Future Garage":   ("Bass", "Garage"),

    # Bass
    "Bass":                          ("Bass", "Leftfield Bass"),
    "Bass Music":                    ("Bass", "Leftfield Bass"),
    "Freeform Bass":                 ("Bass", "Freeform Bass"),
    "Leftfield Bass":                ("Bass", "Leftfield Bass"),

    # Drum & Bass
    "Drum & Bass":                   ("Bass", "Drum & Bass"),
    "DafuQ! [DnB]":                  ("Bass", "Drum & Bass"),

    # Electronic
    "Electronic":                    ("Electronic", "House"),
    "Electonic":                     ("Electronic", "House"),
    "electronic":                    ("Electronic", "House"),
    "House":                         ("Electronic", "House"),
    "Deep House":                    ("Electronic", "Deep House"),
    "Classic Progressive House":     ("Electronic", "Progressive House"),
    "IDM, Downtempo":                ("Electronic", "IDM"),
    "Big Beat":                      ("Electronic", "Big Beat"),
    "Breakbeat":                     ("Electronic", "Breakbeat"),
    "Dance":                         ("Electronic", "House"),

    # Chill
    "Chillout":                      ("Chill", "Chillout"),
    "Chill Out":                     ("Chill", "Chillout"),
    "Chill/The XXX":                 ("Chill", "Chillout"),
    "DafuQ! [Chill]":                ("Chill", "Chillout"),
    "Chillstep":                     ("Chill", "Chillstep"),
    "Chill Step":                    ("Chill", "Chillstep"),
    "Downtempo":                     ("Chill", "Downtempo"),
    "Trip Hop":                      ("Chill", "Trip Hop"),
    "Abstract":                      ("Chill", "Ambient"),

    # Glitch Hop
    "Glitch Hop":                    ("Electronic", "Glitch Hop"),
    "Glitch-Hop":                    ("Electronic", "Glitch Hop"),

    # Trance
    "Psychedelic Trance":            ("Electronic", "Trance"),

    # Hip-Hop
    "Hip-Hop":                       ("Hip-Hop", "Hip-Hop"),
    "Hip-Hop Beats":                 ("Hip-Hop", "Beats"),
    "Beats":                         ("Hip-Hop", "Beats"),
    "Trap":                          ("Hip-Hop", "Trap"),
    "DafuQ! [Trap]":                 ("Hip-Hop", "Trap"),
    "Gangsta":                       ("Hip-Hop", "Hip-Hop"),

    # Dub / Reggae
    "Dub":                           ("Dub/Reggae", "Dub"),
    "Dub / Reggae":                  ("Dub/Reggae", "Dub"),

    # Blues
    "Blues":                         ("Blues/Soul", "Blues"),
    "R&B":                           ("Blues/Soul", "R&B"),

    # Pop / Rock
    "Pop":                           ("Pop/Rock", "Pop"),
    "Country":                       ("Pop/Rock", "Country"),
    "Remix":                         ("Electronic", "House"),

    # DafuQ misc
    "DafuQ! [Hipster]":              ("Pop/Rock", "Indie"),

    # Catch-all
    "Other":                         None,  # unclassifiable
    "Kulemina":                      None,  # label name, not genre
}


# ── DIRECTORY_HINTS ─────────────────────────────────────────────────────────
# Maps directory name patterns (case-insensitive) to (parent, sub).

DIRECTORY_HINTS = {
    "MOBCOIN_DEEP_DUBSTEAP":  ("Bass", "Dubstep"),
    "Downtempo:Lofi":         ("Chill", "Lofi"),
    "deltron":                ("Hip-Hop", "Hip-Hop"),
    "Animatrix":              ("Electronic", "IDM"),
    "NinjaSexParty":          ("Pop/Rock", "Pop"),
}


# ── DISCOGS_TO_KNOB ────────────────────────────────────────────────────────
# Maps Discogs genre labels (as used by MAEST model) to our taxonomy.
# Format: "DiscogsParent---DiscogsLabel" -> (knob_parent, knob_sub)

DISCOGS_TO_KNOB = {
    # Electronic -> Bass
    "Electronic---Dubstep":          ("Bass", "Dubstep"),
    "Electronic---Drum n Bass":      ("Bass", "Drum & Bass"),
    "Electronic---Jungle":           ("Bass", "Drum & Bass"),
    "Electronic---Grime":            ("Bass", "Grime"),
    "Electronic---UK Garage":        ("Bass", "Garage"),
    "Electronic---Speed Garage":     ("Bass", "Garage"),
    "Electronic---Garage House":     ("Bass", "Garage"),
    "Electronic---Bassline":         ("Bass", "Leftfield Bass"),
    "Electronic---Halftime":         ("Bass", "Leftfield Bass"),
    "Electronic---Leftfield":        ("Bass", "Leftfield Bass"),

    # Electronic -> Electronic
    "Electronic---House":            ("Electronic", "House"),
    "Electronic---Deep House":       ("Electronic", "Deep House"),
    "Electronic---Tech House":       ("Electronic", "House"),
    "Electronic---Tribal House":     ("Electronic", "House"),
    "Electronic---Acid House":       ("Electronic", "House"),
    "Electronic---Electro House":    ("Electronic", "House"),
    "Electronic---Euro House":       ("Electronic", "House"),
    "Electronic---Italo House":      ("Electronic", "House"),
    "Electronic---Ghetto House":     ("Electronic", "House"),
    "Electronic---Progressive House":("Electronic", "Progressive House"),
    "Electronic---Trance":           ("Electronic", "Trance"),
    "Electronic---Psy-Trance":       ("Electronic", "Trance"),
    "Electronic---Goa Trance":       ("Electronic", "Trance"),
    "Electronic---Progressive Trance":("Electronic", "Trance"),
    "Electronic---Hard Trance":      ("Electronic", "Trance"),
    "Electronic---Tech Trance":      ("Electronic", "Trance"),
    "Electronic---IDM":              ("Electronic", "IDM"),
    "Electronic---Breakbeat":        ("Electronic", "Breakbeat"),
    "Electronic---Breaks":           ("Electronic", "Breakbeat"),
    "Electronic---Progressive Breaks":("Electronic", "Breakbeat"),
    "Electronic---Big Beat":         ("Electronic", "Big Beat"),
    "Electronic---Glitch":           ("Electronic", "Glitch Hop"),

    # Electronic -> Chill
    "Electronic---Downtempo":        ("Chill", "Downtempo"),
    "Electronic---Ambient":          ("Chill", "Ambient"),
    "Electronic---Dark Ambient":     ("Chill", "Ambient"),
    "Electronic---Chillwave":        ("Chill", "Chillout"),
    "Electronic---Trip Hop":         ("Chill", "Trip Hop"),
    "Electronic---New Age":          ("Chill", "Ambient"),
    "Electronic---Drone":            ("Chill", "Ambient"),

    # Electronic misc
    "Electronic---Techno":           ("Electronic", "House"),
    "Electronic---Minimal Techno":   ("Electronic", "House"),
    "Electronic---Deep Techno":      ("Electronic", "House"),
    "Electronic---Dub Techno":       ("Electronic", "House"),
    "Electronic---Acid":             ("Electronic", "House"),
    "Electronic---Electro":          ("Electronic", "Breakbeat"),
    "Electronic---Disco":            ("Electronic", "House"),
    "Electronic---Nu-Disco":         ("Electronic", "House"),
    "Electronic---Synthwave":        ("Electronic", "House"),
    "Electronic---Synth-pop":        ("Electronic", "House"),
    "Electronic---EBM":              ("Electronic", "House"),
    "Electronic---Industrial":       ("Electronic", "Breakbeat"),
    "Electronic---Noise":            ("Electronic", "IDM"),
    "Electronic---Experimental":     ("Electronic", "IDM"),
    "Electronic---Abstract":         ("Chill", "Ambient"),
    "Electronic---Dub":              ("Dub/Reggae", "Dub"),
    "Electronic---Vaporwave":        ("Chill", "Lofi"),
    "Electronic---Hip Hop":          ("Hip-Hop", "Hip-Hop"),
    "Electronic---Modern Classical": ("Classical", "Modern/Contemporary"),
    "Electronic---Sound Collage":    ("Electronic", "IDM"),

    # Hip Hop
    "Hip Hop---Bass Music":          ("Bass", "Leftfield Bass"),
    "Hip Hop---Boom Bap":            ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Conscious":           ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Gangsta":             ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Hardcore Hip-Hop":    ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Instrumental":        ("Hip-Hop", "Beats"),
    "Hip Hop---Jazzy Hip-Hop":       ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Pop Rap":             ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Trap":                ("Hip-Hop", "Trap"),
    "Hip Hop---Trip Hop":            ("Chill", "Trip Hop"),
    "Hip Hop---Turntablism":         ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Grime":               ("Bass", "Grime"),
    "Hip Hop---Cloud Rap":           ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Cut-up/DJ":           ("Hip-Hop", "Beats"),
    "Hip Hop---G-Funk":              ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Miami Bass":          ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---RnB/Swing":           ("Blues/Soul", "R&B"),
    "Hip Hop---Crunk":               ("Hip-Hop", "Trap"),
    "Hip Hop---Bounce":              ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Electro":             ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Ragga HipHop":        ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Screw":               ("Hip-Hop", "Hip-Hop"),
    "Hip Hop---Thug Rap":            ("Hip-Hop", "Hip-Hop"),

    # Rock -> various
    "Rock---Alternative Rock":       ("Pop/Rock", "Rock"),
    "Rock---Classic Rock":           ("Pop/Rock", "Rock"),
    "Rock---Hard Rock":              ("Pop/Rock", "Rock"),
    "Rock---Indie Rock":             ("Pop/Rock", "Indie"),
    "Rock---Pop Rock":               ("Pop/Rock", "Pop"),
    "Rock---Brit Pop":               ("Pop/Rock", "Pop"),
    "Rock---Grunge":                 ("Pop/Rock", "Rock"),
    "Rock---Garage Rock":            ("Pop/Rock", "Rock"),
    "Rock---Blues Rock":             ("Blues/Soul", "Blues"),
    "Rock---Folk Rock":              ("Pop/Rock", "Folk"),
    "Rock---Country Rock":           ("Pop/Rock", "Country"),
    "Rock---Psychedelic Rock":       ("Pop/Rock", "Rock"),
    "Rock---Prog Rock":              ("Pop/Rock", "Rock"),
    "Rock---Art Rock":               ("Pop/Rock", "Rock"),
    "Rock---Post Rock":              ("Pop/Rock", "Rock"),
    "Rock---Shoegaze":               ("Pop/Rock", "Indie"),
    "Rock---Dream Pop":              ("Pop/Rock", "Indie"),
    "Rock---Soft Rock":              ("Pop/Rock", "Rock"),
    "Rock---Surf":                   ("Pop/Rock", "Rock"),
    "Rock---Rockabilly":             ("Pop/Rock", "Rock"),
    "Rock---Rock & Roll":            ("Pop/Rock", "Rock"),
    "Rock---Acoustic":               ("Pop/Rock", "Folk"),
    "Rock---Southern Rock":          ("Pop/Rock", "Rock"),
    "Rock---Space Rock":             ("Pop/Rock", "Rock"),
    "Rock---Krautrock":              ("Electronic", "IDM"),
    "Rock---New Wave":               ("Pop/Rock", "Pop"),
    "Rock---Lo-Fi":                  ("Chill", "Lofi"),
    "Rock---Math Rock":              ("Pop/Rock", "Rock"),
    "Rock---Noise":                  ("Pop/Rock", "Rock"),
    "Rock---Experimental":           ("Pop/Rock", "Rock"),

    # Rock -> Metal
    "Rock---Heavy Metal":            ("Metal", "Heavy Metal"),
    "Rock---Death Metal":            ("Metal", "Death Metal"),
    "Rock---Black Metal":            ("Metal", "Black Metal"),
    "Rock---Atmospheric Black Metal":("Metal", "Black Metal"),
    "Rock---Depressive Black Metal": ("Metal", "Black Metal"),
    "Rock---Doom Metal":             ("Metal", "Doom"),
    "Rock---Funeral Doom Metal":     ("Metal", "Doom"),
    "Rock---Thrash":                 ("Metal", "Thrash"),
    "Rock---Speed Metal":            ("Metal", "Thrash"),
    "Rock---Stoner Rock":            ("Metal", "Stoner/Sludge"),
    "Rock---Sludge Metal":           ("Metal", "Stoner/Sludge"),
    "Rock---Nu Metal":               ("Metal", "Heavy Metal"),
    "Rock---Power Metal":            ("Metal", "Heavy Metal"),
    "Rock---Progressive Metal":      ("Metal", "Heavy Metal"),
    "Rock---Gothic Metal":           ("Metal", "Heavy Metal"),
    "Rock---Folk Metal":             ("Metal", "Heavy Metal"),
    "Rock---Viking Metal":           ("Metal", "Heavy Metal"),
    "Rock---Funk Metal":             ("Metal", "Heavy Metal"),
    "Rock---Metalcore":              ("Metal", "Heavy Metal"),
    "Rock---Deathcore":              ("Metal", "Death Metal"),
    "Rock---Technical Death Metal":  ("Metal", "Death Metal"),
    "Rock---Melodic Death Metal":    ("Metal", "Death Metal"),
    "Rock---Post-Metal":             ("Metal", "Doom"),
    "Rock---Symphonic Rock":         ("Pop/Rock", "Rock"),
    "Rock---Grindcore":              ("Metal", "Thrash"),
    "Rock---Goregrind":              ("Metal", "Thrash"),

    # Rock -> Punk
    "Rock---Punk":                   ("Punk", "Punk"),
    "Rock---Hardcore":               ("Punk", "Hardcore"),
    "Rock---Post-Hardcore":          ("Punk", "Hardcore"),
    "Rock---Melodic Hardcore":       ("Punk", "Hardcore"),
    "Rock---Post-Punk":              ("Punk", "Post-Punk"),
    "Rock---Crust":                  ("Punk", "Crust"),
    "Rock---Pop Punk":               ("Punk", "Skate Punk"),
    "Rock---Oi":                     ("Punk", "Punk"),
    "Rock---Psychobilly":            ("Punk", "Punk"),
    "Rock---Power Violence":         ("Punk", "Hardcore"),
    "Rock---Emo":                    ("Punk", "Post-Punk"),
    "Rock---Goth Rock":              ("Punk", "Post-Punk"),
    "Rock---Deathrock":              ("Punk", "Post-Punk"),
    "Rock---Coldwave":               ("Punk", "Post-Punk"),

    # Jazz
    "Jazz---Bop":                    ("Jazz", "Bebop"),
    "Jazz---Hard Bop":               ("Jazz", "Bebop"),
    "Jazz---Post Bop":               ("Jazz", "Bebop"),
    "Jazz---Cool Jazz":              ("Jazz", "Cool Jazz"),
    "Jazz---Modal":                  ("Jazz", "Cool Jazz"),
    "Jazz---Free Jazz":              ("Jazz", "Free Jazz"),
    "Jazz---Free Improvisation":     ("Jazz", "Free Jazz"),
    "Jazz---Avant-garde Jazz":       ("Jazz", "Free Jazz"),
    "Jazz---Fusion":                 ("Jazz", "Fusion"),
    "Jazz---Jazz-Funk":              ("Jazz", "Fusion"),
    "Jazz---Jazz-Rock":              ("Jazz", "Fusion"),
    "Jazz---Latin Jazz":             ("Jazz", "Latin Jazz"),
    "Jazz---Afro-Cuban Jazz":        ("Jazz", "Latin Jazz"),
    "Jazz---Swing":                  ("Jazz", "Swing"),
    "Jazz---Big Band":               ("Jazz", "Swing"),
    "Jazz---Dixieland":              ("Jazz", "Swing"),
    "Jazz---Smooth Jazz":            ("Jazz", "Cool Jazz"),
    "Jazz---Soul-Jazz":              ("Jazz", "Fusion"),
    "Jazz---Contemporary Jazz":      ("Jazz", "Cool Jazz"),
    "Jazz---Bossa Nova":             ("Jazz", "Latin Jazz"),
    "Jazz---Gypsy Jazz":             ("Jazz", "Swing"),
    "Jazz---Ragtime":                ("Jazz", "Swing"),
    "Jazz---Afrobeat":               ("Jazz", "Fusion"),
    "Jazz---Space-Age":              ("Jazz", "Cool Jazz"),
    "Jazz---Easy Listening":         ("Jazz", "Cool Jazz"),

    # Classical
    "Classical---Baroque":           ("Classical", "Orchestral"),
    "Classical---Classical":         ("Classical", "Orchestral"),
    "Classical---Romantic":          ("Classical", "Orchestral"),
    "Classical---Impressionist":     ("Classical", "Orchestral"),
    "Classical---Modern":            ("Classical", "Modern/Contemporary"),
    "Classical---Contemporary":      ("Classical", "Modern/Contemporary"),
    "Classical---Post-Modern":       ("Classical", "Modern/Contemporary"),
    "Classical---Neo-Classical":      ("Classical", "Modern/Contemporary"),
    "Classical---Neo-Romantic":      ("Classical", "Orchestral"),
    "Classical---Medieval":          ("Classical", "Chamber"),
    "Classical---Renaissance":       ("Classical", "Chamber"),
    "Classical---Choral":            ("Classical", "Chamber"),
    "Classical---Opera":             ("Classical", "Opera"),

    # Blues
    "Blues---Chicago Blues":          ("Blues/Soul", "Blues"),
    "Blues---Delta Blues":            ("Blues/Soul", "Blues"),
    "Blues---Electric Blues":         ("Blues/Soul", "Blues"),
    "Blues---Country Blues":          ("Blues/Soul", "Blues"),
    "Blues---Texas Blues":            ("Blues/Soul", "Blues"),
    "Blues---Modern Electric Blues":  ("Blues/Soul", "Blues"),
    "Blues---Piano Blues":            ("Blues/Soul", "Blues"),
    "Blues---Jump Blues":             ("Blues/Soul", "Blues"),
    "Blues---Harmonica Blues":        ("Blues/Soul", "Blues"),
    "Blues---Louisiana Blues":        ("Blues/Soul", "Blues"),
    "Blues---Boogie Woogie":         ("Blues/Soul", "Blues"),
    "Blues---Rhythm & Blues":         ("Blues/Soul", "R&B"),

    # Funk / Soul
    "Funk / Soul---Funk":            ("Blues/Soul", "Funk"),
    "Funk / Soul---Soul":            ("Blues/Soul", "Soul"),
    "Funk / Soul---Rhythm & Blues":  ("Blues/Soul", "R&B"),
    "Funk / Soul---Contemporary R&B":("Blues/Soul", "R&B"),
    "Funk / Soul---Disco":           ("Blues/Soul", "Funk"),
    "Funk / Soul---Boogie":          ("Blues/Soul", "Funk"),
    "Funk / Soul---P.Funk":          ("Blues/Soul", "Funk"),
    "Funk / Soul---Free Funk":       ("Blues/Soul", "Funk"),
    "Funk / Soul---Neo Soul":        ("Blues/Soul", "Soul"),
    "Funk / Soul---Psychedelic":     ("Blues/Soul", "Funk"),
    "Funk / Soul---Gospel":          ("Blues/Soul", "Soul"),
    "Funk / Soul---Afrobeat":        ("Blues/Soul", "Funk"),
    "Funk / Soul---New Jack Swing":  ("Blues/Soul", "R&B"),
    "Funk / Soul---Swingbeat":       ("Blues/Soul", "R&B"),
    "Funk / Soul---UK Street Soul":  ("Blues/Soul", "Soul"),

    # Reggae
    "Reggae---Dub":                  ("Dub/Reggae", "Dub"),
    "Reggae---Reggae":               ("Dub/Reggae", "Reggae"),
    "Reggae---Roots Reggae":         ("Dub/Reggae", "Reggae"),
    "Reggae---Dancehall":            ("Dub/Reggae", "Reggae"),
    "Reggae---Ska":                  ("Dub/Reggae", "Reggae"),
    "Reggae---Rocksteady":           ("Dub/Reggae", "Reggae"),
    "Reggae---Lovers Rock":          ("Dub/Reggae", "Reggae"),
    "Reggae---Ragga":                ("Dub/Reggae", "Reggae"),
    "Reggae---Reggae-Pop":           ("Dub/Reggae", "Reggae"),
    "Reggae---Calypso":              ("Dub/Reggae", "Reggae"),
    "Reggae---Soca":                 ("Dub/Reggae", "Reggae"),

    # Pop
    "Pop---Ballad":                  ("Pop/Rock", "Pop"),
    "Pop---Indie Pop":               ("Pop/Rock", "Indie"),
    "Pop---Vocal":                   ("Pop/Rock", "Pop"),
    "Pop---Europop":                 ("Pop/Rock", "Pop"),
    "Pop---Chanson":                 ("Pop/Rock", "Pop"),
    "Pop---City Pop":                ("Pop/Rock", "Pop"),
    "Pop---J-pop":                   ("Pop/Rock", "Pop"),
    "Pop---K-pop":                   ("Pop/Rock", "Pop"),
    "Pop---Schlager":                ("Pop/Rock", "Pop"),
    "Pop---Bubblegum":               ("Pop/Rock", "Pop"),
    "Pop---Light Music":             ("Pop/Rock", "Pop"),
    "Pop---Novelty":                 ("Pop/Rock", "Pop"),
    "Pop---Bollywood":               ("Pop/Rock", "Pop"),

    # Folk / Country
    "Folk, World, & Country---Folk": ("Pop/Rock", "Folk"),
    "Folk, World, & Country---Country": ("Pop/Rock", "Country"),
    "Folk, World, & Country---Bluegrass": ("Pop/Rock", "Country"),
    "Folk, World, & Country---Celtic": ("Pop/Rock", "Folk"),
    "Folk, World, & Country---Gospel": ("Blues/Soul", "Soul"),
    "Folk, World, & Country---Honky Tonk": ("Pop/Rock", "Country"),
    "Folk, World, & Country---Hillbilly": ("Pop/Rock", "Country"),
    "Folk, World, & Country---Nordic": ("Pop/Rock", "Folk"),
    "Folk, World, & Country---African": ("Blues/Soul", "Funk"),
    "Folk, World, & Country---Highlife": ("Blues/Soul", "Funk"),
    "Folk, World, & Country---Fado": ("Pop/Rock", "Folk"),
    "Folk, World, & Country---Flamenco": ("Pop/Rock", "Folk"),

    # Latin -> various
    "Latin---Bossanova":             ("Jazz", "Latin Jazz"),
    "Latin---Salsa":                 ("Jazz", "Latin Jazz"),
    "Latin---Afro-Cuban":            ("Jazz", "Latin Jazz"),
    "Latin---Cumbia":                ("Pop/Rock", "Folk"),
    "Latin---Tango":                 ("Pop/Rock", "Folk"),
    "Latin---Reggaeton":             ("Hip-Hop", "Hip-Hop"),
    "Latin---Samba":                 ("Jazz", "Latin Jazz"),

    # Non-Music (these shouldn't appear on music tracks, but map them anyway)
    "Non-Music---Spoken Word":       None,
    "Non-Music---Comedy":            None,
    "Non-Music---Audiobook":         None,
    "Non-Music---Dialogue":          None,
    "Non-Music---Interview":         None,
    "Non-Music---Field Recording":   None,
    "Non-Music---Poetry":            None,
    "Non-Music---Radioplay":         None,
    "Non-Music---Promotional":       None,
    "Non-Music---Education":         None,
    "Non-Music---Monolog":           None,
    "Non-Music---Political":         None,
    "Non-Music---Religious":         None,

    # Stage & Screen
    "Stage & Screen---Soundtrack":   ("Classical", "Orchestral"),
    "Stage & Screen---Score":        ("Classical", "Orchestral"),
    "Stage & Screen---Musical":      ("Pop/Rock", "Pop"),
    "Stage & Screen---Theme":        ("Pop/Rock", "Pop"),

    # Brass & Military
    "Brass & Military---Brass Band": ("Jazz", "Swing"),
    "Brass & Military---Marches":    ("Classical", "Orchestral"),
    "Brass & Military---Military":   ("Classical", "Orchestral"),
}


def normalize_tag(raw_genre):
    """Normalize a raw genre string to (parent, sub) or None."""
    if not raw_genre:
        return None
    raw = raw_genre.strip()
    result = TAG_NORMALIZE.get(raw)
    if result is not None:
        return result
    # Try case-insensitive lookup
    raw_lower = raw.lower()
    for tag, mapping in TAG_NORMALIZE.items():
        if tag.lower() == raw_lower:
            return mapping
    return None


def directory_hint(dirpath):
    """Check if a directory path contains genre hints. Returns (parent, sub) or None."""
    for hint_dir, genre in DIRECTORY_HINTS.items():
        if hint_dir.lower() in dirpath.lower():
            return genre
    return None


def content_type_from_dir(dirpath):
    """Check if a directory indicates non-music content. Returns content_type string or None."""
    parts = dirpath.replace("\\", "/").split("/")
    for part in parts:
        if part in CONTENT_TYPE_DIRS:
            return CONTENT_TYPE_DIRS[part]
    return None


def discogs_to_knob(discogs_label):
    """Map a Discogs genre label to our taxonomy. Returns (parent, sub) or None."""
    return DISCOGS_TO_KNOB.get(discogs_label)
