#!/usr/bin/env python3
"""
Builds data/species_data.json — the local body-length + silhouette-shape table
the app reads at display time. Run once (or again after editing SPECIES below):

    python3 build_species_data.py

To find species that need a row — run this after every new batch of art, since
a bundle always brings birds this table has never heard of:

    python3 build_species_data.py --audit

No network, no API. Lengths are average total body length in inches (bill to
tail), curated for Colorado Front Range species. "shape" picks one of the
built-in silhouettes in app/vendor/silhouettes/. Anything the live eBird feed
reports that isn't in this table falls back to a generic songbird silhouette
scaled to a default length — so the app never breaks on an unlisted bird; that
species just looks generic until you add a row here and re-run.

Keyed by lowercase scientific binomial so matching is case-insensitive.
"""
import json
import os
import sys

# What server.py falls back to for a species with no row here — kept in step
# with enrich() so the audit below can name the number.
DEFAULT_LEN = 8

# sci (binomial)                 -> (common name, length_in, shape)
SPECIES = {
    # ---- Waterfowl -----------------------------------------------------
    "anser caerulescens":        ("Snow Goose", 28, "waterfowl"),
    "anser rossii":              ("Ross's Goose", 23, "waterfowl"),
    "anser albifrons":           ("Greater White-fronted Goose", 28, "waterfowl"),
    "branta hutchinsii":         ("Cackling Goose", 25, "waterfowl"),
    "branta canadensis":         ("Canada Goose", 40, "waterfowl"),
    "cygnus buccinator":         ("Trumpeter Swan", 60, "waterfowl"),
    "cygnus columbianus":        ("Tundra Swan", 52, "waterfowl"),
    "aix sponsa":                ("Wood Duck", 18.5, "waterfowl"),
    "spatula discors":           ("Blue-winged Teal", 15.5, "waterfowl"),
    "spatula cyanoptera":        ("Cinnamon Teal", 16, "waterfowl"),
    "spatula clypeata":          ("Northern Shoveler", 19, "waterfowl"),
    "mareca strepera":           ("Gadwall", 20, "waterfowl"),
    "mareca americana":          ("American Wigeon", 20, "waterfowl"),
    "anas platyrhynchos":        ("Mallard", 23, "waterfowl"),
    "anas acuta":                ("Northern Pintail", 21, "waterfowl"),
    "anas crecca":               ("Green-winged Teal", 14, "waterfowl"),
    "aythya valisineria":        ("Canvasback", 21, "waterfowl"),
    "aythya americana":          ("Redhead", 19, "waterfowl"),
    "aythya collaris":           ("Ring-necked Duck", 17, "waterfowl"),
    "aythya affinis":            ("Lesser Scaup", 16.5, "waterfowl"),
    "aythya marila":             ("Greater Scaup", 18, "waterfowl"),
    "bucephala albeola":         ("Bufflehead", 13.5, "waterfowl"),
    "bucephala clangula":        ("Common Goldeneye", 18.5, "waterfowl"),
    "bucephala islandica":       ("Barrow's Goldeneye", 18, "waterfowl"),
    "lophodytes cucullatus":     ("Hooded Merganser", 18, "waterfowl"),
    "mergus merganser":          ("Common Merganser", 25, "waterfowl"),
    "mergus serrator":           ("Red-breasted Merganser", 23, "waterfowl"),
    "oxyura jamaicensis":        ("Ruddy Duck", 15, "waterfowl"),

    # ---- Gamebirds -----------------------------------------------------
    "callipepla squamata":       ("Scaled Quail", 10, "gamebird"),
    "colinus virginianus":       ("Northern Bobwhite", 9.75, "gamebird"),
    "meleagris gallopavo":       ("Wild Turkey", 46, "gamebird"),
    "tympanuchus phasianellus":  ("Sharp-tailed Grouse", 17, "gamebird"),
    "centrocercus urophasianus": ("Greater Sage-Grouse", 26, "gamebird"),
    "dendragapus obscurus":      ("Dusky Grouse", 20, "gamebird"),
    "phasianus colchicus":       ("Ring-necked Pheasant", 30, "gamebird"),

    # ---- Grebes / loons / cormorants / pelicans ------------------------
    "podilymbus podiceps":       ("Pied-billed Grebe", 13, "waterfowl"),
    "podiceps nigricollis":      ("Eared Grebe", 12.5, "waterfowl"),
    "podiceps auritus":          ("Horned Grebe", 14, "waterfowl"),
    "aechmophorus occidentalis": ("Western Grebe", 25, "waterfowl"),
    "aechmophorus clarkii":      ("Clark's Grebe", 25, "waterfowl"),
    "gavia immer":               ("Common Loon", 32, "waterfowl"),
    "nannopterum auritum":       ("Double-crested Cormorant", 33, "wader"),
    "pelecanus erythrorhynchos": ("American White Pelican", 62, "wader"),

    # ---- Wading birds --------------------------------------------------
    "botaurus lentiginosus":     ("American Bittern", 28, "wader"),
    "ardea herodias":            ("Great Blue Heron", 46, "wader"),
    "ardea alba":                ("Great Egret", 39, "wader"),
    "egretta thula":             ("Snowy Egret", 24, "wader"),
    "bubulcus ibis":             ("Cattle Egret", 20, "wader"),
    "butorides virescens":       ("Green Heron", 18, "wader"),
    "nycticorax nycticorax":     ("Black-crowned Night-Heron", 25, "wader"),
    "plegadis chihi":            ("White-faced Ibis", 23, "wader"),
    "antigone canadensis":       ("Sandhill Crane", 46, "wader"),

    # ---- Raptors -------------------------------------------------------
    "cathartes aura":            ("Turkey Vulture", 27, "raptor"),
    "pandion haliaetus":         ("Osprey", 23, "raptor"),
    "aquila chrysaetos":         ("Golden Eagle", 30, "raptor"),
    "circus hudsonius":          ("Northern Harrier", 18, "raptor"),
    "accipiter striatus":        ("Sharp-shinned Hawk", 11, "raptor"),
    "accipiter cooperii":        ("Cooper's Hawk", 16.5, "raptor"),
    "astur atricapillus":        ("Northern Goshawk", 21, "raptor"),
    "haliaeetus leucocephalus":  ("Bald Eagle", 31, "raptor"),
    "buteo lineatus":            ("Red-shouldered Hawk", 17, "raptor"),
    "buteo platypterus":         ("Broad-winged Hawk", 15, "raptor"),
    "buteo swainsoni":           ("Swainson's Hawk", 19, "raptor"),
    "buteo jamaicensis":         ("Red-tailed Hawk", 19, "raptor"),
    "buteo regalis":             ("Ferruginous Hawk", 23, "raptor"),
    "buteo lagopus":             ("Rough-legged Hawk", 21, "raptor"),
    "falco sparverius":          ("American Kestrel", 9, "falcon"),
    "falco columbarius":         ("Merlin", 10, "falcon"),
    "falco mexicanus":           ("Prairie Falcon", 16, "falcon"),
    "falco peregrinus":          ("Peregrine Falcon", 16, "falcon"),

    # ---- Owls ----------------------------------------------------------
    "megascops kennicottii":     ("Western Screech-Owl", 8.5, "owl"),
    "bubo virginianus":          ("Great Horned Owl", 22, "owl"),
    "athene cunicularia":        ("Burrowing Owl", 9.5, "owl"),
    "strix nebulosa":            ("Great Gray Owl", 27, "owl"),
    "asio otus":                 ("Long-eared Owl", 15, "owl"),
    "asio flammeus":             ("Short-eared Owl", 15, "owl"),
    "aegolius acadicus":         ("Northern Saw-whet Owl", 8, "owl"),

    # ---- Shorebirds ----------------------------------------------------
    "charadrius vociferus":      ("Killdeer", 10.5, "shorebird"),
    "charadrius semipalmatus":   ("Semipalmated Plover", 7.25, "shorebird"),
    "himantopus mexicanus":      ("Black-necked Stilt", 14, "shorebird"),
    "recurvirostra americana":   ("American Avocet", 18, "shorebird"),
    "bartramia longicauda":      ("Upland Sandpiper", 12, "shorebird"),
    "numenius americanus":       ("Long-billed Curlew", 23, "shorebird"),
    "limosa fedoa":              ("Marbled Godwit", 18, "shorebird"),
    "calidris bairdii":          ("Baird's Sandpiper", 7.5, "shorebird"),
    "calidris minutilla":        ("Least Sandpiper", 6, "shorebird"),
    "limnodromus scolopaceus":   ("Long-billed Dowitcher", 11.5, "shorebird"),
    "gallinago delicata":        ("Wilson's Snipe", 11, "shorebird"),
    "actitis macularius":        ("Spotted Sandpiper", 7.5, "shorebird"),
    "tringa melanoleuca":        ("Greater Yellowlegs", 14, "shorebird"),
    "tringa flavipes":           ("Lesser Yellowlegs", 10.5, "shorebird"),
    "phalaropus tricolor":       ("Wilson's Phalarope", 9.25, "shorebird"),

    # ---- Gulls / terns -------------------------------------------------
    "chroicocephalus philadelphia": ("Bonaparte's Gull", 13, "gull"),
    "leucophaeus pipixcan":      ("Franklin's Gull", 14.5, "gull"),
    "larus delawarensis":        ("Ring-billed Gull", 18, "gull"),
    "larus californicus":        ("California Gull", 21, "gull"),
    "larus argentatus":          ("Herring Gull", 25, "gull"),
    "hydroprogne caspia":        ("Caspian Tern", 21, "gull"),
    "sterna forsteri":           ("Forster's Tern", 14.5, "gull"),
    "chlidonias niger":          ("Black Tern", 9.75, "gull"),

    # ---- Doves / pigeons -----------------------------------------------
    "patagioenas fasciata":      ("Band-tailed Pigeon", 14.5, "dove"),
    "columba livia":             ("Rock Pigeon", 12.5, "dove"),
    "streptopelia decaocto":     ("Eurasian Collared-Dove", 13, "dove"),
    "zenaida macroura":          ("Mourning Dove", 12, "dove"),
    "columbina inca":            ("Inca Dove", 8.25, "dove"),

    # ---- Cuckoos / nightjars / swifts / hummingbirds -------------------
    "coccyzus americanus":       ("Yellow-billed Cuckoo", 12, "songbird"),
    "chordeiles minor":          ("Common Nighthawk", 9.5, "swallow"),
    "phalaenoptilus nuttallii":  ("Common Poorwill", 7.75, "swallow"),
    "aeronautes saxatalis":      ("White-throated Swift", 6.5, "swallow"),
    "cypseloides niger":         ("Black Swift", 7.25, "swallow"),
    "archilochus alexandri":     ("Black-chinned Hummingbird", 3.75, "hummingbird"),
    "calypte anna":              ("Anna's Hummingbird", 4, "hummingbird"),
    "selasphorus platycercus":   ("Broad-tailed Hummingbird", 4, "hummingbird"),
    "selasphorus rufus":         ("Rufous Hummingbird", 3.75, "hummingbird"),
    "selasphorus calliope":      ("Calliope Hummingbird", 3.25, "hummingbird"),

    # ---- Kingfisher / woodpeckers --------------------------------------
    "megaceryle alcyon":         ("Belted Kingfisher", 13, "woodpecker"),
    "melanerpes lewis":          ("Lewis's Woodpecker", 10.75, "woodpecker"),
    "melanerpes erythrocephalus":("Red-headed Woodpecker", 9.25, "woodpecker"),
    "melanerpes carolinus":      ("Red-bellied Woodpecker", 9.25, "woodpecker"),
    "sphyrapicus nuchalis":      ("Red-naped Sapsucker", 8.5, "woodpecker"),
    "dryobates pubescens":       ("Downy Woodpecker", 6.75, "woodpecker"),
    "dryobates villosus":        ("Hairy Woodpecker", 9.25, "woodpecker"),
    "colaptes auratus":          ("Northern Flicker", 12.5, "woodpecker"),

    # ---- Flycatchers ---------------------------------------------------
    "contopus cooperi":          ("Olive-sided Flycatcher", 7.5, "songbird"),
    "contopus sordidulus":       ("Western Wood-Pewee", 6.25, "songbird"),
    "empidonax traillii":        ("Willow Flycatcher", 5.75, "songbird"),
    "empidonax minimus":         ("Least Flycatcher", 5.25, "songbird"),
    "sayornis saya":             ("Say's Phoebe", 7.5, "songbird"),
    "myiarchus cinerascens":     ("Ash-throated Flycatcher", 8.25, "songbird"),
    "tyrannus verticalis":       ("Western Kingbird", 8.75, "songbird"),
    "tyrannus tyrannus":         ("Eastern Kingbird", 8.5, "songbird"),

    # ---- Shrikes / vireos ----------------------------------------------
    "lanius ludovicianus":       ("Loggerhead Shrike", 9, "songbird"),
    "lanius borealis":           ("Northern Shrike", 9.5, "songbird"),
    "vireo plumbeus":            ("Plumbeous Vireo", 5.25, "songbird"),
    "vireo gilvus":              ("Warbling Vireo", 5.5, "songbird"),

    # ---- Corvids -------------------------------------------------------
    "perisoreus canadensis":     ("Canada Jay", 11.5, "corvid"),
    "cyanocitta stelleri":       ("Steller's Jay", 11.5, "corvid"),
    "cyanocitta cristata":       ("Blue Jay", 11, "corvid"),
    "aphelocoma woodhouseii":    ("Woodhouse's Scrub-Jay", 11.5, "corvid"),
    "gymnorhinus cyanocephalus": ("Pinyon Jay", 10.5, "corvid"),
    "nucifraga columbiana":      ("Clark's Nutcracker", 12, "corvid"),
    "pica hudsonia":             ("Black-billed Magpie", 19, "corvid"),
    "corvus brachyrhynchos":     ("American Crow", 17.5, "corvid"),
    "corvus corax":              ("Common Raven", 24, "corvid"),

    # ---- Larks / swallows ----------------------------------------------
    "eremophila alpestris":      ("Horned Lark", 7.25, "songbird"),
    "tachycineta bicolor":       ("Tree Swallow", 5.75, "swallow"),
    "tachycineta thalassina":    ("Violet-green Swallow", 5.25, "swallow"),
    "stelgidopteryx serripennis":("Northern Rough-winged Swallow", 5.5, "swallow"),
    "riparia riparia":           ("Bank Swallow", 5.25, "swallow"),
    "petrochelidon pyrrhonota":  ("Cliff Swallow", 5.5, "swallow"),
    "hirundo rustica":           ("Barn Swallow", 6.75, "swallow"),

    # ---- Chickadees / nuthatches / wrens / kinglets --------------------
    "poecile atricapillus":      ("Black-capped Chickadee", 5.25, "songbird"),
    "poecile gambeli":           ("Mountain Chickadee", 5.25, "songbird"),
    "baeolophus ridgwayi":       ("Juniper Titmouse", 5.75, "songbird"),
    "psaltriparus minimus":      ("Bushtit", 4.5, "songbird"),
    "sitta canadensis":          ("Red-breasted Nuthatch", 4.5, "songbird"),
    "sitta carolinensis":        ("White-breasted Nuthatch", 5.75, "songbird"),
    "sitta pygmaea":             ("Pygmy Nuthatch", 4.25, "songbird"),
    "certhia americana":         ("Brown Creeper", 5.25, "songbird"),
    "salpinctes obsoletus":      ("Rock Wren", 6, "songbird"),
    "catherpes mexicanus":       ("Canyon Wren", 5.75, "songbird"),
    "troglodytes aedon":         ("House Wren", 4.75, "songbird"),
    "cistothorus palustris":     ("Marsh Wren", 5, "songbird"),
    "thryomanes bewickii":       ("Bewick's Wren", 5.25, "songbird"),
    "polioptila caerulea":       ("Blue-gray Gnatcatcher", 4.25, "songbird"),
    "regulus satrapa":           ("Golden-crowned Kinglet", 4, "songbird"),
    "corthylio calendula":       ("Ruby-crowned Kinglet", 4.25, "songbird"),

    # ---- Dippers / thrushes / mimids / starlings -----------------------
    "cinclus mexicanus":         ("American Dipper", 7.5, "songbird"),
    "sialia sialis":             ("Eastern Bluebird", 7, "songbird"),
    "sialia mexicana":           ("Western Bluebird", 7, "songbird"),
    "sialia currucoides":        ("Mountain Bluebird", 7.25, "songbird"),
    "myadestes townsendi":       ("Townsend's Solitaire", 8.5, "songbird"),
    "catharus guttatus":         ("Hermit Thrush", 6.75, "songbird"),
    "turdus migratorius":        ("American Robin", 10, "songbird"),
    "dumetella carolinensis":    ("Gray Catbird", 8.5, "songbird"),
    "toxostoma curvirostre":     ("Curve-billed Thrasher", 11, "songbird"),
    "oreoscoptes montanus":      ("Sage Thrasher", 8.5, "songbird"),
    "mimus polyglottos":         ("Northern Mockingbird", 10, "songbird"),
    "sturnus vulgaris":          ("European Starling", 8.5, "songbird"),
    "bombycilla cedrorum":       ("Cedar Waxwing", 7.25, "songbird"),
    "bombycilla garrulus":       ("Bohemian Waxwing", 8.25, "songbird"),
    "anthus rubescens":          ("American Pipit", 6.5, "songbird"),

    # ---- Finches -------------------------------------------------------
    "haemorhous mexicanus":      ("House Finch", 6, "songbird"),
    "haemorhous cassinii":       ("Cassin's Finch", 6.25, "songbird"),
    "leucosticte tephrocotis":   ("Gray-crowned Rosy-Finch", 6.25, "songbird"),
    "leucosticte atrata":        ("Black Rosy-Finch", 6.25, "songbird"),
    "leucosticte australis":     ("Brown-capped Rosy-Finch", 6.25, "songbird"),
    "acanthis flammea":          ("Common Redpoll", 5.25, "songbird"),
    "spinus pinus":              ("Pine Siskin", 5, "songbird"),
    "spinus psaltria":           ("Lesser Goldfinch", 4.5, "songbird"),
    "spinus tristis":            ("American Goldfinch", 5, "songbird"),
    "loxia curvirostra":         ("Red Crossbill", 6.25, "songbird"),
    "coccothraustes vespertinus":("Evening Grosbeak", 8, "songbird"),

    # ---- Sparrows / towhees --------------------------------------------
    "peucaea cassinii":          ("Cassin's Sparrow", 6, "songbird"),
    "spizelloides arborea":      ("American Tree Sparrow", 6.25, "songbird"),
    "spizella passerina":        ("Chipping Sparrow", 5.5, "songbird"),
    "spizella pallida":          ("Clay-colored Sparrow", 5.5, "songbird"),
    "spizella pusilla":          ("Field Sparrow", 5.75, "songbird"),
    "spizella breweri":          ("Brewer's Sparrow", 5.5, "songbird"),
    "chondestes grammacus":      ("Lark Sparrow", 6.5, "songbird"),
    "calamospiza melanocorys":   ("Lark Bunting", 7, "songbird"),
    "passerculus sandwichensis": ("Savannah Sparrow", 5.5, "songbird"),
    "pooecetes gramineus":       ("Vesper Sparrow", 6.25, "songbird"),
    "ammospiza nelsoni":         ("Nelson's Sparrow", 5, "songbird"),
    "passerella iliaca":         ("Fox Sparrow", 7, "songbird"),
    "spizella atrogularis":      ("Black-chinned Sparrow", 5.75, "songbird"),
    "melospiza melodia":         ("Song Sparrow", 6.25, "songbird"),
    "melospiza lincolnii":       ("Lincoln's Sparrow", 5.75, "songbird"),
    "melospiza georgiana":       ("Swamp Sparrow", 5.75, "songbird"),
    "zonotrichia albicollis":    ("White-throated Sparrow", 6.75, "songbird"),
    "zonotrichia querula":       ("Harris's Sparrow", 7.5, "songbird"),
    "zonotrichia leucophrys":    ("White-crowned Sparrow", 7, "songbird"),
    "junco hyemalis":            ("Dark-eyed Junco", 6.25, "songbird"),
    "amphispiza bilineata":      ("Black-throated Sparrow", 5.5, "songbird"),
    "artemisiospiza nevadensis": ("Sagebrush Sparrow", 5.25, "songbird"),
    "pipilo chlorurus":          ("Green-tailed Towhee", 7.25, "songbird"),
    "pipilo maculatus":          ("Spotted Towhee", 8.5, "songbird"),

    # ---- Blackbirds / meadowlarks / orioles ----------------------------
    "dolichonyx oryzivorus":     ("Bobolink", 7, "songbird"),
    "sturnella neglecta":        ("Western Meadowlark", 9.5, "songbird"),
    "xanthocephalus xanthocephalus": ("Yellow-headed Blackbird", 9.5, "songbird"),
    "agelaius phoeniceus":       ("Red-winged Blackbird", 8.75, "songbird"),
    "molothrus ater":            ("Brown-headed Cowbird", 7.5, "songbird"),
    "euphagus cyanocephalus":    ("Brewer's Blackbird", 9, "songbird"),
    "quiscalus quiscula":        ("Common Grackle", 12.5, "songbird"),
    "quiscalus mexicanus":       ("Great-tailed Grackle", 18, "songbird"),
    "icterus bullockii":         ("Bullock's Oriole", 8.75, "songbird"),
    "icterus galbula":           ("Baltimore Oriole", 8.75, "songbird"),

    # ---- Wood-warblers -------------------------------------------------
    "mniotilta varia":           ("Black-and-white Warbler", 5.25, "songbird"),
    "leiothlypis celata":        ("Orange-crowned Warbler", 5, "songbird"),
    "leiothlypis virginiae":     ("Virginia's Warbler", 4.75, "songbird"),
    "geothlypis trichas":        ("Common Yellowthroat", 5, "songbird"),
    "setophaga petechia":        ("Yellow Warbler", 5, "songbird"),
    "setophaga coronata":        ("Yellow-rumped Warbler", 5.5, "songbird"),
    "setophaga nigrescens":      ("Black-throated Gray Warbler", 5, "songbird"),
    "setophaga townsendi":       ("Townsend's Warbler", 5, "songbird"),
    "cardellina pusilla":        ("Wilson's Warbler", 4.75, "songbird"),
    "icteria virens":            ("Yellow-breasted Chat", 7.5, "songbird"),

    # ---- Tanagers / grosbeaks / buntings -------------------------------
    "piranga ludoviciana":       ("Western Tanager", 7.25, "songbird"),
    "pheucticus melanocephalus": ("Black-headed Grosbeak", 8.25, "songbird"),
    "pheucticus ludovicianus":   ("Rose-breasted Grosbeak", 8, "songbird"),
    "passerina caerulea":        ("Blue Grosbeak", 6.75, "songbird"),
    "passerina amoena":          ("Lazuli Bunting", 5.5, "songbird"),
    "passerina cyanea":          ("Indigo Bunting", 5.5, "songbird"),
    "spiza americana":           ("Dickcissel", 6.25, "songbird"),
    "cardinalis cardinalis":     ("Northern Cardinal", 8.75, "songbird"),
    "passer domesticus":         ("House Sparrow", 6.25, "songbird"),

    # ---- additions from the size audit (2026-07-05) --------------------
    "tyto furcata":              ("American Barn Owl", 16, "owl"),
    "megascops asio":            ("Eastern Screech-Owl", 8.5, "owl"),
    "psiloscops flammeolus":     ("Flammulated Owl", 6.75, "owl"),
    "glaucidium gnoma":          ("Northern Pygmy-Owl", 6.75, "owl"),
    "empidonax hammondii":       ("Hammond's Flycatcher", 5.5, "songbird"),
    "empidonax oberholseri":     ("Dusky Flycatcher", 5.75, "songbird"),
    "pyrocephalus rubinus":      ("Vermilion Flycatcher", 6, "songbird"),
    "setophaga ruticilla":       ("American Redstart", 5.25, "songbird"),
    "setophaga citrina":         ("Hooded Warbler", 5.25, "songbird"),
    "geothlypis tolmiei":        ("MacGillivray's Warbler", 5.25, "songbird"),
    "seiurus aurocapilla":       ("Ovenbird", 6, "songbird"),
    "ammodramus savannarum":     ("Grasshopper Sparrow", 5, "songbird"),
    "chaetura pelagica":         ("Chimney Swift", 5.25, "swallow"),
    "dryobates scalaris":        ("Ladder-backed Woodpecker", 7.25, "woodpecker"),
    "sphyrapicus thyroideus":    ("Williamson's Sapsucker", 9.5, "woodpecker"),
    "zenaida asiatica":          ("White-winged Dove", 11.5, "dove"),
    "caracara plancus":          ("Crested Caracara", 23, "raptor"),
    "sterna hirundo":            ("Common Tern", 12.5, "gull"),
    "nannopterum brasilianum":   ("Neotropic Cormorant", 25, "wader"),
    "calidris pusilla":          ("Semipalmated Sandpiper", 6.25, "shorebird"),
    "calidris mauri":            ("Western Sandpiper", 6.5, "shorebird"),
    "calidris fuscicollis":      ("White-rumped Sandpiper", 7.5, "shorebird"),
    "porzana carolina":          ("Sora", 8.75, "shorebird"),
    "rallus limicola":           ("Virginia Rail", 9.5, "shorebird"),

    # ---- additions from the upload size audit (2026-07-05) -------------
    "sterna paradisaea":         ("Arctic Tern", 15, "gull"),
    "geothlypis formosa":        ("Kentucky Warbler", 5.25, "songbird"),
    "vireo flavifrons":          ("Yellow-throated Vireo", 5.5, "songbird"),

    # waterfowl that were defaulting to 8" (Graylag also catches its hybrids,
    # which share the "Anser anser" binomial)
    "anser anser":               ("Graylag Goose", 33, "waterfowl"),
    "cygnus olor":               ("Mute Swan", 55, "waterfowl"),
    "branta bernicla":           ("Brant", 25, "waterfowl"),

    # ---- eastern species added with the US-FL art bundle (audit 2026-08-22) --
    # These arrived on the board with the new illustrations and had no row, so
    # every one of them drew at the generic 8" fallback: a Red-necked Grebe came
    # out the size of a Semipalmated Plover, and a White Ibis the size of a
    # warbler. Lengths are average total body length, bill to tail, matching the
    # convention above; shapes follow their nearest relatives already listed.
    "fulica americana":          ("American Coot", 15.5, "waterfowl"),
    "podiceps grisegena":        ("Red-necked Grebe", 18, "waterfowl"),
    "eudocimus albus":           ("White Ibis", 25, "wader"),
    "nyctanassa violacea":       ("Yellow-crowned Night Heron", 24, "wader"),
    "ictinia mississippiensis":  ("Mississippi Kite", 14, "raptor"),
    "pluvialis squatarola":      ("Black-bellied Plover", 11.5, "shorebird"),
    "calidris melanotos":        ("Pectoral Sandpiper", 8.75, "shorebird"),
    "calidris himantopus":       ("Stilt Sandpiper", 8.5, "shorebird"),
    "tringa solitaria":          ("Solitary Sandpiper", 8.5, "shorebird"),
    "picoides dorsalis":         ("American Three-toed Woodpecker", 8.75, "woodpecker"),
    "tyrannus forficatus":       ("Scissor-tailed Flycatcher", 13, "songbird"),
    "sayornis phoebe":           ("Eastern Phoebe", 7, "songbird"),
    "contopus virens":           ("Eastern Wood-Pewee", 6.25, "songbird"),
    "vireo olivaceus":           ("Red-eyed Vireo", 5, "songbird"),
    "vireo swainsoni":           ("Western Warbling Vireo", 5.5, "songbird"),
    "toxostoma rufum":           ("Brown Thrasher", 11.5, "songbird"),
    "melopsittacus undulatus":   ("Budgerigar", 7, "songbird"),
    "setophaga pensylvanica":    ("Chestnut-sided Warbler", 5, "songbird"),
    "setophaga americana":       ("Northern Parula", 4.5, "songbird"),
    "setophaga aestiva":         ("Northern Yellow Warbler", 5, "songbird"),
    "icterus spurius":           ("Orchard Oriole", 7.25, "songbird"),

    # ---- every bundled illustration now has a length (audit 2026-07-05) ------
    # covers eBird genus renames (Astur, Leuconotopicus, Hesperiphona, Ardea
    # ibis, Leiothlypis, Nannopterum…) plus the repo's West-coast species, so
    # nothing renders at the 8" default if it turns up nearby.
    "astur cooperii":            ("Cooper's Hawk", 16.5, "raptor"),
    "astur gentilis":            ("American Goshawk", 21, "raptor"),
    "leuconotopicus villosus":   ("Hairy Woodpecker", 9.25, "woodpecker"),
    "hesperiphona vespertina":   ("Evening Grosbeak", 8, "songbird"),
    "ardea ibis":                ("Cattle Egret", 20, "wader"),
    "leiothlypis luciae":        ("Lucy's Warbler", 4.25, "songbird"),
    "leiothlypis ruficapilla":   ("Nashville Warbler", 4.75, "songbird"),
    "aphelocoma californica":    ("California Scrub-Jay", 11.5, "corvid"),
    "artemisiospiza belli":      ("Bell's Sparrow", 5, "songbird"),
    "baeolophus inornatus":      ("Oak Titmouse", 5.75, "songbird"),
    "calidris alba":             ("Sanderling", 8, "shorebird"),
    "calidris alpina":           ("Dunlin", 8.5, "shorebird"),
    "callipepla californica":    ("California Quail", 10, "gamebird"),
    "calothorax lucifer":        ("Lucifer Hummingbird", 3.5, "hummingbird"),
    "calypte costae":            ("Costa's Hummingbird", 3.5, "hummingbird"),
    "cardellina rubrifrons":     ("Red-faced Warbler", 5.5, "songbird"),
    "catharus ustulatus":        ("Swainson's Thrush", 7, "songbird"),
    "chaetura vauxi":            ("Vaux's Swift", 4.75, "swallow"),
    "columbina passerina":       ("Common Ground Dove", 6.5, "dove"),
    "coragyps atratus":          ("Black Vulture", 25, "raptor"),
    "dryobates nuttallii":       ("Nuttall's Woodpecker", 7.5, "woodpecker"),
    "dryocopus pileatus":        ("Pileated Woodpecker", 16.5, "woodpecker"),
    "egretta caerulea":          ("Little Blue Heron", 24, "wader"),
    "elanus leucurus":           ("White-tailed Kite", 15, "raptor"),
    "empidonax difficilis":      ("Pacific-slope Flycatcher", 5.5, "songbird"),
    "empidonax wrightii":        ("Gray Flycatcher", 6, "songbird"),
    "gymnogyps californianus":   ("California Condor", 46, "raptor"),
    "haemorhous purpureus":      ("Purple Finch", 6, "songbird"),
    "icterus cucullatus":        ("Hooded Oriole", 8, "songbird"),
    "icterus parisorum":         ("Scott's Oriole", 9, "songbird"),
    "ixoreus naevius":           ("Varied Thrush", 9.5, "songbird"),
    "larus glaucescens":         ("Glaucous-winged Gull", 26, "gull"),
    "larus heermanni":           ("Heermann's Gull", 19, "gull"),
    "larus occidentalis":        ("Western Gull", 25, "gull"),
    "leucophaeus atricilla":     ("Laughing Gull", 16.5, "gull"),
    "melanerpes formicivorus":   ("Acorn Woodpecker", 9, "woodpecker"),
    "melozone aberti":           ("Abert's Towhee", 9.5, "songbird"),
    "melozone crissalis":        ("California Towhee", 9, "songbird"),
    "melozone fusca":            ("Canyon Towhee", 8.5, "songbird"),
    "pelecanus occidentalis":    ("Brown Pelican", 51, "wader"),
    "phainopepla nitens":        ("Phainopepla", 7.75, "songbird"),
    "pica nuttalli":             ("Yellow-billed Magpie", 16.5, "corvid"),
    "picoides arcticus":         ("Black-backed Woodpecker", 9.5, "woodpecker"),
    "pinicola enucleator":       ("Pine Grosbeak", 9, "songbird"),
    "pipilo erythrophthalmus":   ("Eastern Towhee", 8, "songbird"),
    "piranga rubra":             ("Summer Tanager", 7.75, "songbird"),
    "poecile rufescens":         ("Chestnut-backed Chickadee", 4.75, "songbird"),
    "progne subis":              ("Purple Martin", 8, "swallow"),
    "rynchops niger":            ("Black Skimmer", 18, "gull"),
    "sayornis nigricans":        ("Black Phoebe", 6.75, "songbird"),
    "selasphorus sasin":         ("Allen's Hummingbird", 3.75, "hummingbird"),
    "setophaga magnolia":        ("Magnolia Warbler", 5, "songbird"),
    "setophaga occidentalis":    ("Hermit Warbler", 5, "songbird"),
    "setophaga palmarum":        ("Palm Warbler", 5.5, "songbird"),
    "sphyrapicus ruber":         ("Red-breasted Sapsucker", 8.5, "woodpecker"),
    "spinus lawrencei":          ("Lawrence's Goldfinch", 4.75, "songbird"),
    "strix occidentalis":        ("Spotted Owl", 17, "owl"),
    "thalasseus elegans":        ("Elegant Tern", 17, "gull"),
    "toxostoma redivivum":       ("California Thrasher", 12, "songbird"),
    "tringa semipalmata":        ("Willet", 15, "shorebird"),
    "troglodytes pacificus":     ("Pacific Wren", 4, "songbird"),
    "tyrannus vociferans":       ("Cassin's Kingbird", 9, "songbird"),
    "tyto alba":                 ("Barn Owl", 16, "owl"),
    "urile penicillatus":        ("Brandt's Cormorant", 34, "wader"),
    "vireo bellii":              ("Bell's Vireo", 4.75, "songbird"),
    "vireo cassinii":            ("Cassin's Vireo", 5.25, "songbird"),
    "vireo huttoni":             ("Hutton's Vireo", 5, "songbird"),
    "zonotrichia atricapilla":   ("Golden-crowned Sparrow", 7, "songbird"),
}


def audit(here):
    """Every species the atlas has recorded that has no row here.

    Those birds are not broken — they draw at DEFAULT_LEN with a generic
    songbird silhouette — but the fallback is invisible on screen, and on a
    board whose whole premise is scale a wrong size reads as fact. Worth
    running after any new batch of art, because a bundle brings species this
    table has never heard of.
    """
    atlas_path = os.path.join(here, "data", "atlas.json")
    if not os.path.exists(atlas_path):
        print("No data/atlas.json yet — nothing recorded to audit.")
        return 0
    atlas = json.load(open(atlas_path))
    missing = []
    for entry in atlas.values():
        sci = " ".join((entry.get("sciName") or "").lower().split()[:2])
        if sci and sci not in SPECIES:
            missing.append((entry.get("comName") or "?", sci))
    if not missing:
        print(f"All {len(atlas)} species recorded here have a length. Nothing to add.")
        return 0
    print(f"{len(missing)} of {len(atlas)} recorded species have no row and draw "
          f'at the generic {DEFAULT_LEN}" fallback:\n')
    for common, sci in sorted(missing):
        print(f'    "{sci}":{" " * max(1, 28 - len(sci))}("{common}", ?, "?"),')
    print("\nAdd them to SPECIES above with a real body length (bill to tail) and\n"
          "a shape from app/vendor/silhouettes/, then re-run without --audit.")
    return 1


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    if "--audit" in sys.argv:
        return audit(here)
    out = os.path.join(here, "data", "species_data.json")
    table = {
        sci: {"common": common, "lengthIn": length, "shape": shape}
        for sci, (common, length, shape) in SPECIES.items()
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(table, f, indent=0, sort_keys=True)
    print(f"Wrote {len(table)} species to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
