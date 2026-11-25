# i18n.py
# Internationalisation (i18n) of the game: all player-visible texts, in French and English.
# Keys are English identifiers; the text is looked up with get_text(key).

# French texts
FR = {
    "title_game": "Écho",
    "pause_host_ip": "Adresse de la partie : {ip}",
    "slot_empty": "[ Emplacement Vide ]",
    "slot_checkpoint": "Checkpoint : {name}",
    "checkpoint_zone": "Zone {id}",
    "checkpoint_10_46": "Point de Départ",
    "checkpoint_1_12": "Entrée de la Grotte",
    "checkpoint_80_10": "Salle du Boss",
    "net_error_timeout": "Timeout : {host} ne répond pas.\nVérifiez le pare-feu et la redirection de port.",
    "net_error_refused": "Connexion refusée : {host}\nLe serveur n'est pas démarré.",
    "net_error_address": "Adresse invalide : '{host}'",
    "net_error_full": "Le serveur est plein !\n(3/3 joueurs)",
    "net_error_version": "Version incompatible avec le serveur.\nMettez le jeu à jour.",
    "net_error_network": "Impossible de se connecter\nau serveur : {host}",
    "net_error_relay": "Échec connexion relay :\n{detail}",
    "net_error_lost": "Connexion perdue.",
    
    # Main menu
    "menu_heberger": "Héberger une partie",
    "menu_join": "Rejoindre une partie",
    "menu_settings": "Paramètres",
    "menu_quit": "Quitter",
    "menu_new_game": "Nouvelle Partie",
    "menu_continue": "Continuer",

    # Slots menu
    "slots_title_new": "Choisir un emplacement",
    "slots_title_continue": "Charger une partie",
    "slots_launch": "Lancer",
    "slots_confirm_overwrite": "Cette sauvegarde existe. Écraser ?",

    # Profile menu
    "param_section_profile": "--- Profil ---",
    "param_nickname": "Pseudo",
    "param_appearance": "Apparence",

    # Join menu
    "join_title": "Rejoindre une partie",
    "join_label_ip": "Entrez l'IP de l'hôte (vide pour 'localhost'):",
    "join_label_code": "Entrez le code room :",
    "join_connect": "Se connecter",
    "join_back": "Retour",
    "join_mode_ip": "Mode : IP directe",
    "join_mode_code": "Mode : Code Room",
    "join_code_invalide": "Code invalide",
    "join_label_ip_relay": "IP de l'hôte :",
    "param_code_room_label": "Code partie :",
    "param_code_room_empty": "Partie non lancée",

    # Pause menu
    "pause_title": "Pause",
    "pause_resume": "Reprendre",
    "pause_settings": "Paramètres",
    "pause_quit_session": "Quitter la session",
    "pause_terminer_session": "Mettre fin à la session",

    # Settings menu
    "param_title": "Paramètres",
    "param_section_gameplay": "--- Jouabilité ---",
    "param_language": "Langue : Français",
    "param_section_net": "--- Réseau ---",
    "param_section_video": "--- Vidéo ---",
    "param_resolution": "Résolution",
    "param_fullscreen": "Plein écran",
    "param_screen": "Écran",
    "param_screen_redemarrage": "Le changement d'écran sera appliqué au prochain lancement",
    "param_vsync": "VSync (Non implémenté)",
    "param_brightness": "Luminosité",
    "param_brightness_title": "Ajuster la luminosité",
    "param_brightness_help": "Glissez le curseur, puis Appliquer",
    "param_section_controls": "--- Contrôles ---",
    "param_left": "Gauche",
    "param_right": "Droite",
    "param_jump": "Saut",
    "param_echo": "Écho",
    "param_attack": "Attaque",
    "param_dash": "Dash",
    "param_echo_dir": "Écho Directionnel",
    "param_apply": "Appliquer",
    "param_back": "Retour",
    "param_waiting_key": "[ ... ]",
    "param_yes": "OUI",
    "param_not": "NON",

    # Confirmation popup
    "popup_title": "Attention",
    "popup_message": "Voulez-vous écraser cette sauvegarde ?",
    "popup_yes": "Oui",
    "popup_not": "Non",

    "skin_scout": "Éclaireur",
    "skin_specter": "Spectre",

    # Lore : textes des stèles et lettres
    "lore_stele": ["Ici repose le serment des Premiers Éclaireurs.", "", "« Nous étions cinq quand le Silence tomba.", "  Nous avons cru que nos voix suffiraient", "  à tenir l'obscurité à distance.", "", "  Nous avions tort.", "", "  Le dernier d'entre nous grave ces mots", "  pour celui qui viendra après :", "", "  L'écho n'est pas une arme.", "  C'est un souvenir.", "  Et les souvenirs ne meurent jamais", "  tant qu'il reste quelqu'un pour les entendre. »", "", "                    — Aelys, Dernière Éclaireure,", "                      An 1 du Grand Silence"],
    "lore_stele_dash": ["Ici fut gravé le Pas de l'Éclaireur.", "", "« Avant que le Silence nous engloutisse,", "  nous courions entre les ombres.", "  Pas pour fuir —", "  pour exister encore une seconde de plus.", "", "  Ce mouvement n'est pas une technique.", "  C'est un réflexe de survivant.", "  Le corps qui refuse de s'arrêter", "  quand tout lui dit de tomber.", "", "  Si tu lis ces mots,", "  c'est que tu as encore quelque chose", "  qui vaut la peine d'être couru. »", "", "                    — Aelys, Dernière Éclaireure,", "                      An 1 du Grand Silence"],
    "lore_letter_jonas": ["Papa,", "", "Si tu lis ces mots, c'est que tu es allé plus loin que je ne l'espérais.", "Plus loin que moi.", "", "Je t'écris depuis les profondeurs, là où SOLARIS ne regarde plus.", "Ils pensent que personne ne descend jusqu'ici. Ils ont tort.", "", "J'ai trouvé quelque chose. Une créature, immense, qui rôde dans les zones", "les plus obscures des tunnels. Elle n'est pas comme les Nocturnes.", "Elle est différente. Plus ancienne. Je ne sais pas si SOLARIS l'a créée", "ou si elle existait avant eux — avant le Voile Noir, avant tout ça.", "Mais une chose est certaine : elle garde quelque chose.", "", "Je n'ai pas pu aller plus loin. Pas seul.", "", "Papa, je ne t'ai jamais demandé de me suivre dans ce combat.", "Je sais ce que ça t'a coûté. Mais si tu es là, si tu as trouvé ce message,", "c'est que tu cherches encore. C'est que tu n'as pas abandonné.", "", "Alors ne t'arrête pas maintenant.", "", "Ce que SOLARIS nous a volé — le soleil, la liberté, les gens qu'on aimait —", "tout ça est quelque part au bout de ces tunnels. Je le sens.", "", "Va jusqu'au bout. Pour nous deux.", "Pour tous ceux qui n'ont plus la force de le faire.", "", "                    — Jonas"],
    "lore_lever": ["Fragment de Mémoire — Secteur 7", "", "« Ils ont scellé ce couloir à deux reprises.", "  Une serrure ne suffisait pas, disaient-ils.", "  Deux mains, deux volontés, deux cœurs.", "  Seulement alors, le passage s'ouvre.", "", "  J'ai vu les mécanismes de mes propres yeux.", "  Deux bras de fer, aux extrémités opposées.", "  Ni l'un avant l'autre.", "  Ni l'un sans l'autre.", "  Ensemble, et seulement ensemble.", "", "  Ils avaient peur de ce qui se trouve derrière.", "  À raison. »", "", "— Inscription gravée par un ancien ouvrier de SOLARIS"],
    "lore_title_inscription": "✦   Inscription Traduite   ✦",
    "lore_sub_inscription": "— Message gravé en Langue des Éclaireurs —",
    "lore_title_fragment": "✦   Fragment de Mémoire   ✦",
    "lore_sub_sector7": "— Secteur 7 —",
    "lore_title_letter": "✦   Lettre de Jonas   ✦",
    "lore_sub_letter": "— Trouvée dans les profondeurs —",

    # Lore : popups d'interaction
    "lore_popup_fragment": "Fragment de Mémoire",
    "lore_popup_dash_msg": "Absorber ce souvenir — {cost} âmes ?",
    "lore_popup_stele": "Stèle Mystérieuse",
    "lore_popup_pay_msg": "Payer {cost} âmes pour déchiffrer ?",
    "lore_popup_echo": "L'écho des anciens coulera en vous.",
    "lore_btn_pay": "Payer",
    "lore_btn_give_up": "Renoncer",
    "lore_hint_confirm": "[Entrée] Confirmer  |  [Échap] Annuler",
    "lore_hint_close": "[ Échap ] ou cliquer en dehors pour fermer",
    "lore_poor_title": "!  Âmes insuffisantes",
    "lore_poor_need": "Il vous faut {cost} âmes.",
    "lore_poor_keep_going": "Continuez votre chemin...",
    "lore_unlocked_title": "✦  Mémoire absorbée  ✦",
    "lore_unlocked_sub": "Vous portez désormais le pas des Éclaireurs.",

    # Lore : panneau boutique (stèle des améliorations)
    "lore_sign_upgrades": "[{key}]  Améliorations",
    "lore_sign_shop_dash": "[{key}]  {cost} âmes",
    "lore_sign_read": "[{key}]  Lire",
    "lore_shop_title": "✦  Forgeron de l'Écho  ✦",
    "lore_shop_bought": "Acheté",
    "lore_shop_buy": "Acheter [{n}]",
    "lore_shop_no_funds": "Fonds insuffisants",
    "lore_shop_max": "Max atteint",
    "lore_shop_damage": "Force de frappe doublée",
    "lore_shop_once": "{cost} âmes  —  une seule fois",
    "lore_shop_hp": "PV Maximum +1",
    "lore_shop_hp_count": "{cost} âmes  —  {n}/{max} acheté(s)",
    "lore_shop_echo_dir": "Écho Directionnel",
    "lore_shop_hint": "Appuyer sur 1 / 2 / 3 pour acheter  —  [ Échap ] pour fermer",

    # Notifications de capacités
    "notif_dash_title": "Pas de l'Éclaireur absorbé",
    "notif_dash_sub": "Le souffle des anciens vous porte — Dash",
    "notif_double_jump_title": "Mémoire du bond retrouvée",
    "notif_double_jump_sub": "L'élan des Éclaireurs vous habite — Double Saut",
    "notif_key_title": "Clé des profondeurs trouvée",
    "notif_key_sub": "Une porte vous attend quelque part — Clé",
    "notif_echo_dir_title": "Écho Directionnel débloqué",
    "notif_echo_dir_sub": "Votre voix perce l'obscurité — Écho Directionnel",
    "notif_default_title": "Capacité débloquée",
    "orb_price": "{cost} âmes",
    "quest_reward_title": "Quêtes accomplies !",
    "quest_reward_sub": "+{money} âmes — merci d'avoir joué",

    # Fin de partie
    "end_message": ["Solaris est détruit.", "", "La lumière qui vous avait emprisonnés ici", "s'est éteinte pour toujours.", "", "Vous êtes libres."],

    # HUD
    "hud_souls": "Âmes : {n}",
    "hud_echo_dir_title": "ÉCH.DIR",
    "hud_ready": "PRÊT",
    "hud_key": "Clé",
    "hud_end": "FIN merci d'avoir joué",

    # Menu : contrôles et copie IP
    "menu_ctrl_interact": "Interagir (Pancarte)",
    "menu_ctrl_torch": "Torche",
    "menu_ctrl_journal": "Journal des quêtes",
    "menu_ip_local": "IP Locale (LAN) :",
    "menu_copied": "(Copié)",
    "menu_copy": "(copier)",
    "menu_click_copy": "Cliquez pour copier dans le presse-papiers",

    # Journal de quêtes
    "quest_label": "QUÊTES",
    "quest_title": "Journal de Quête",
    "quest_sub": "— Chroniques de l'Éclaireur —",
    "quest_enemies_text": "Vaincs 5 ennemis",
    "quest_enemies_detail": ["Les ruines grouillent de créatures corrompues", "par le Grand Silence. Prouve ta valeur en", "éliminant cinq d'entre elles."],
    "quest_enemies_progress": "Vaincs 5 ennemis  ({n}/5)",
    "quest_souls_text": "Récolte 50 âmes",
    "quest_souls_detail": ["Les âmes errantes sont la monnaie des morts.", "Ramasse-en cinquante pour prouver", "que tu maîtrises les ténèbres."],
    "quest_souls_progress": "Récolte 50 âmes  ({n}/50)",
    "quest_key_item_text": "Trouve la clé",
    "quest_key_item_detail": ["Une vieille clé en fer forgé se trouve", "quelque part dans les ruines. Elle est", "le seul moyen d'ouvrir la Porte de l'Aurore."],
    "quest_door_text": "Ouvre la Porte de l'Aurore",
    "quest_door_detail": ["La Porte de l'Aurore est scellée depuis", "des siècles au fond des ruines. Derrière", "elle se trouve la source de la Première Lumière."],

    # Tutoriel : boutons et titres
    "tuto_btn_next": "Suivant  >>",
    "tuto_btn_back": "<<  Retour",
    "tuto_btn_start": "Commencer !",
    "tuto_btn_skip": "Passer ×",
    "tuto_gameplay_title": "Mécaniques de jeu",
    "tuto_gameplay_sub": "Tout ce dont tu as besoin pour survivre dans l'obscurité",
    "tuto_lore_title": "L'Univers d'Écho",
    "tuto_lore_sub": "L'histoire et le monde derrière l'obscurité",
    "tuto_badge_controls": "  CONTRÔLES",
    "tuto_badge_combat": "  COMBAT & SURVIE",
    "tuto_badge_echolocation": "  ÉCHOLOCALISATION",
    "tuto_badge_lost_souls": "  ÂMES PERDUES",
    "tuto_badge_progress": "  CAPACITÉS & PROGRESSION",
    "tuto_badge_silence": "  LE GRAND SILENCE",
    "tuto_badge_gate": "  LA PORTE INTERDITE",
    "tuto_badge_scout": "  TU ES L'ÉCLAIREUR",
    "tuto_badge_wandering": "  LES ÂMES ERRANTES",

    # Tutoriel : contrôles
    "tuto_ctrl_move": "Déplacement horizontal",
    "tuto_ctrl_jump": "Saut  ·  ×2 si Double Saut",
    "tuto_ctrl_dash": "Dash  ·  si débloqué",
    "tuto_ctrl_echo": "Écho radial — révèle l'environnement",
    "tuto_ctrl_echo_dir": "Écho directionnel  ·  si débloqué",
    "tuto_ctrl_attack": "Attaque de mêlée",
    "tuto_ctrl_pause": "Pause",
    "tuto_key_escape": "[ ÉCHAP ]",
    "tuto_hp_lines": [["Tu as ", "5 PV", ". Chaque contact en retire 1."], ["", "1 s", " d'invincibilité après un coup."]],
    "tuto_enemy_hp_lines": [["1 PV", "— patrouilleurs rapides"], ["2 PV", "— gardes standard"], ["3 PV", "— gardiens lourds"]],

    # Tutoriel : écholocalisation et textes
    "tuto_echo_intro": "Le monde est dans le noir absolu.\nActive l'écho pour révéler l'environnement.",
    "tuto_echo_radial_info": "Radial : 360°, 150 px, cd 2.5 s",
    "tuto_echo_dir_info": "Directionnel : ±25°, 300 px, cd 4 s  (débloquable)",
    "tuto_lost_souls_text": "À ta mort → une âme apparaît\navec tout ton argent.\nAttaque-la pour récupérer —\nou mourir = perte définitive.",
    "tuto_progress_text": "Orbe (dans le monde) → Double Saut.\nShop (pancarte, âmes) → Dash (50 â),\nécho dir. (10 â), PV+ (20 â)...\n\nLa porte verrouillée exige la clé.\nCheckpoints → sauvegarde auto.",
    "tuto_silence_text": "Il y a cent ans, le « Grand Silence »\na plongé le monde dans une obscurité\ntotale et permanente.\n\nLes villes sont devenues des labyrinthes\npeuplés de créatures corrompues\npar l'absence de lumière.",
    "tuto_gate_text": "Au cœur des ruines :\n« La Porte de l'Aurore ».\n\nDerrière elle, la Première Lumière —\nseule capable d'inverser le Silence.",
    "tuto_scout_text": "Tu maîtrises l'Art de l'Écho —\nune technique permettant de percevoir\nle monde par le son.\n\nLà où les autres voient le néant,\ntoi tu entends contours et dangers.",
    "tuto_wandering_text": "Ce sont des âmes corrompues par\nle Silence, piégées entre deux mondes.\n\nEn les vaincant tu libères leur énergie.",
    "tuto_cta_lines": ["Traverse les ruines. Bats les gardiens.", "Trouve la clé. Ouvre la Porte.", "Ramène la lumière."],
}

# English texts
EN = {
    "title_game": "Echo",
    "pause_host_ip": "Game address: {ip}",
    "slot_empty": "[ Empty Slot ]",
    "slot_checkpoint": "Checkpoint: {name}",
    "checkpoint_zone": "Zone {id}",
    "checkpoint_10_46": "Starting Point",
    "checkpoint_1_12": "Cave Entrance",
    "checkpoint_80_10": "Boss Room",
    "net_error_timeout": "Timeout: {host} is not responding.\nCheck the firewall and port forwarding.",
    "net_error_refused": "Connection refused: {host}\nThe server is not running.",
    "net_error_address": "Invalid address: '{host}'",
    "net_error_full": "The server is full!\n(3/3 players)",
    "net_error_version": "Incompatible server version.\nPlease update the game.",
    "net_error_network": "Could not connect\nto the server: {host}",
    "net_error_relay": "Relay connection failed:\n{detail}",
    "net_error_lost": "Connection lost.",
    
    # Main Menu
    "menu_heberger": "Host a game",
    "menu_join": "Join a game",
    "menu_settings": "Settings",
    "menu_quit": "Quit",
    "menu_new_game": "New Game",
    "menu_continue": "Continue",

    # Menu Slots
    "slots_title_new": "Choose a slot",
    "slots_title_continue": "Load a game",
    "slots_launch": "Launch",
    "slots_confirm_overwrite": "This save exists. Overwrite?",

    # Profile Menu
    "param_section_profile": "--- Profile ---",
    "param_nickname": "Username",
    "param_appearance": "Appearance",

    # Join Menu
    "join_title": "Join a game",
    "join_label_ip": "Enter host IP (empty for 'localhost'):",
    "join_label_code": "Enter room code:",
    "join_connect": "Connect",
    "join_back": "Back",
    "join_mode_ip": "Mode: Direct IP",
    "join_mode_code": "Mode: Room Code",
    "join_code_invalide": "Invalid code",
    "join_label_ip_relay": "Host IP:",
    "param_code_room_label": "Game code:",
    "param_code_room_empty": "No game running",

    # Pause Menu
    "pause_title": "Paused",
    "pause_resume": "Resume",
    "pause_settings": "Settings",
    "pause_quit_session": "Quit Session",
    "pause_terminer_session": "End Session",

    # Settings Menu
    "param_title": "Settings",
    "param_section_gameplay": "--- Gameplay ---",
    "param_language": "Language: English",
    "param_section_net": "--- Network ---",
    "param_section_video": "--- Video ---",
    "param_resolution": "Resolution",
    "param_fullscreen": "Fullscreen",
    "param_screen": "Display",
    "param_screen_redemarrage": "Display change will apply on next launch",
    "param_vsync": "VSync (Not implemented)",
    "param_brightness": "Brightness",
    "param_brightness_title": "Adjust brightness",
    "param_brightness_help": "Drag the slider, then Apply",
    "param_section_controls": "--- Controls ---",
    "param_left": "Left",
    "param_right": "Right",
    "param_jump": "Jump",
    "param_echo": "Echo",
    "param_attack": "Attack",
    "param_dash": "Dash",
    "param_echo_dir": "Directional Echo",
    "param_apply": "Apply",
    "param_back": "Back",
    "param_waiting_key": "[ ... ]",
    "param_yes": "YES",
    "param_not": "NO",

    # Popup Confirmation
    "popup_title": "Warning",
    "popup_message": "Do you want to overwrite this save?",
    "popup_yes": "Yes",
    "popup_not": "No",

    "skin_scout": "Scout",
    "skin_specter": "Specter",

    # Lore : textes des stèles et lettres
    "lore_stele": ["Here rests the oath of the First Scouts.", "", "\"We were five when the Silence fell.", "  We believed our voices would be enough", "  to hold the darkness at a distance.", "", "  We were wrong.", "", "  The last of us carves these words", "  for whoever comes after:", "", "  The echo is not a weapon.", "  It is a memory.", "  And memories never die", "  as long as someone is left to hear them.\"", "", "                    — Aelys, Last Scout,", "                      Year 1 of the Great Silence"],
    "lore_stele_dash": ["Here was carved the Scout's Step.", "", "\"Before the Silence swallowed us,", "  we ran between the shadows.", "  Not to flee —", "  to exist one second longer.", "", "  This movement is not a technique.", "  It is a survivor's reflex.", "  A body that refuses to stop", "  when everything tells it to fall.", "", "  If you are reading these words,", "  then you still have something", "  worth running for.\"", "", "                    — Aelys, Last Scout,", "                      Year 1 of the Great Silence"],
    "lore_letter_jonas": ["Dad,", "", "If you are reading these words, you have gone further than I hoped.", "Further than I did.", "", "I am writing to you from the depths, where SOLARIS no longer looks.", "They think no one comes down this far. They are wrong.", "", "I found something. A creature, enormous, prowling the darkest parts", "of the tunnels. It is not like the Nocturnes.", "It is different. Older. I don't know whether SOLARIS created it,", "or whether it existed before them — before the Black Veil, before all of this.", "But one thing is certain: it is guarding something.", "", "I could not go further. Not alone.", "", "Dad, I never asked you to follow me into this fight.", "I know what it cost you. But if you are here, if you found this message,", "then you are still searching. You have not given up.", "", "So don't stop now.", "", "What SOLARIS stole from us — the sun, freedom, the people we loved —", "all of it lies at the end of these tunnels. I can feel it.", "", "Go all the way. For both of us.", "For everyone who no longer has the strength to.", "", "                    — Jonas"],
    "lore_lever": ["Memory Fragment — Sector 7", "", "\"They sealed this corridor twice.", "  A single lock was not enough, they said.", "  Two hands, two wills, two hearts.", "  Only then does the passage open.", "", "  I saw the mechanisms with my own eyes.", "  Two iron arms, at opposite ends.", "  Neither before the other.", "  Neither without the other.", "  Together, and only together.", "", "  They feared what lies beyond.", "  Rightly so.\"", "", "— Inscription carved by a former SOLARIS worker"],
    "lore_title_inscription": "✦   Translated Inscription   ✦",
    "lore_sub_inscription": "— Message carved in the Scouts' Tongue —",
    "lore_title_fragment": "✦   Memory Fragment   ✦",
    "lore_sub_sector7": "— Sector 7 —",
    "lore_title_letter": "✦   Jonas's Letter   ✦",
    "lore_sub_letter": "— Found in the depths —",

    # Lore : popups d'interaction
    "lore_popup_fragment": "Memory Fragment",
    "lore_popup_dash_msg": "Absorb this memory — {cost} souls?",
    "lore_popup_stele": "Mysterious Stele",
    "lore_popup_pay_msg": "Pay {cost} souls to decipher it?",
    "lore_popup_echo": "The echo of the ancients will flow through you.",
    "lore_btn_pay": "Pay",
    "lore_btn_give_up": "Give up",
    "lore_hint_confirm": "[Enter] Confirm  |  [Esc] Cancel",
    "lore_hint_close": "[ Esc ] or click outside to close",
    "lore_poor_title": "!  Not enough souls",
    "lore_poor_need": "You need {cost} souls.",
    "lore_poor_keep_going": "Keep on your way...",
    "lore_unlocked_title": "✦  Memory absorbed  ✦",
    "lore_unlocked_sub": "You now walk in the Scouts' footsteps.",

    # Lore : panneau boutique (stèle des améliorations)
    "lore_sign_upgrades": "[{key}]  Upgrades",
    "lore_sign_shop_dash": "[{key}]  {cost} souls",
    "lore_sign_read": "[{key}]  Read",
    "lore_shop_title": "✦  Echo Blacksmith  ✦",
    "lore_shop_bought": "Bought",
    "lore_shop_buy": "Buy [{n}]",
    "lore_shop_no_funds": "Insufficient funds",
    "lore_shop_max": "Maxed out",
    "lore_shop_damage": "Strike power doubled",
    "lore_shop_once": "{cost} souls  —  one time only",
    "lore_shop_hp": "Max HP +1",
    "lore_shop_hp_count": "{cost} souls  —  {n}/{max} bought",
    "lore_shop_echo_dir": "Directional Echo",
    "lore_shop_hint": "Press 1 / 2 / 3 to buy  —  [ Esc ] to close",

    # Notifications de capacités
    "notif_dash_title": "Scout's Step absorbed",
    "notif_dash_sub": "The breath of the ancients carries you — Dash",
    "notif_double_jump_title": "Memory of the leap recovered",
    "notif_double_jump_sub": "The Scouts' momentum lives in you — Double Jump",
    "notif_key_title": "Key of the depths found",
    "notif_key_sub": "A door awaits you somewhere — Key",
    "notif_echo_dir_title": "Directional Echo unlocked",
    "notif_echo_dir_sub": "Your voice pierces the darkness — Directional Echo",
    "notif_default_title": "Ability unlocked",
    "orb_price": "{cost} souls",
    "quest_reward_title": "Quests completed!",
    "quest_reward_sub": "+{money} souls — thanks for playing",

    # Fin de partie
    "end_message": ["Solaris is destroyed.", "", "The light that imprisoned you here", "has gone out forever.", "", "You are free."],

    # HUD
    "hud_souls": "Souls: {n}",
    "hud_echo_dir_title": "DIR.ECHO",
    "hud_ready": "READY",
    "hud_key": "Key",
    "hud_end": "END — thanks for playing",

    # Menu : contrôles et copie IP
    "menu_ctrl_interact": "Interact (Sign)",
    "menu_ctrl_torch": "Torch",
    "menu_ctrl_journal": "Quest journal",
    "menu_ip_local": "Local IP (LAN):",
    "menu_copied": "(Copied)",
    "menu_copy": "(copy)",
    "menu_click_copy": "Click to copy to the clipboard",

    # Journal de quêtes
    "quest_label": "QUESTS",
    "quest_title": "Quest Journal",
    "quest_sub": "— Chronicles of the Scout —",
    "quest_enemies_text": "Defeat 5 enemies",
    "quest_enemies_detail": ["The ruins swarm with creatures corrupted", "by the Great Silence. Prove your worth by", "eliminating five of them."],
    "quest_enemies_progress": "Defeat 5 enemies  ({n}/5)",
    "quest_souls_text": "Collect 50 souls",
    "quest_souls_detail": ["Wandering souls are the currency of the dead.", "Gather fifty of them to prove", "that you master the darkness."],
    "quest_souls_progress": "Collect 50 souls  ({n}/50)",
    "quest_key_item_text": "Find the key",
    "quest_key_item_detail": ["An old wrought-iron key lies", "somewhere in the ruins. It is", "the only way to open the Gate of Dawn."],
    "quest_door_text": "Open the Gate of Dawn",
    "quest_door_detail": ["The Gate of Dawn has been sealed for", "centuries deep in the ruins. Behind it", "lies the source of the First Light."],

    # Tutoriel : boutons et titres
    "tuto_btn_next": "Next  >>",
    "tuto_btn_back": "<<  Back",
    "tuto_btn_start": "Start!",
    "tuto_btn_skip": "Skip ×",
    "tuto_gameplay_title": "Game mechanics",
    "tuto_gameplay_sub": "Everything you need to survive in the darkness",
    "tuto_lore_title": "The World of Echo",
    "tuto_lore_sub": "The story and the world behind the darkness",
    "tuto_badge_controls": "  CONTROLS",
    "tuto_badge_combat": "  COMBAT & SURVIVAL",
    "tuto_badge_echolocation": "  ECHOLOCATION",
    "tuto_badge_lost_souls": "  LOST SOULS",
    "tuto_badge_progress": "  ABILITIES & PROGRESSION",
    "tuto_badge_silence": "  THE GREAT SILENCE",
    "tuto_badge_gate": "  THE FORBIDDEN GATE",
    "tuto_badge_scout": "  YOU ARE THE SCOUT",
    "tuto_badge_wandering": "  WANDERING SOULS",

    # Tutoriel : contrôles
    "tuto_ctrl_move": "Horizontal movement",
    "tuto_ctrl_jump": "Jump  ·  ×2 with Double Jump",
    "tuto_ctrl_dash": "Dash  ·  once unlocked",
    "tuto_ctrl_echo": "Radial echo — reveals the surroundings",
    "tuto_ctrl_echo_dir": "Directional echo  ·  once unlocked",
    "tuto_ctrl_attack": "Melee attack",
    "tuto_ctrl_pause": "Pause",
    "tuto_key_escape": "[ ESC ]",
    "tuto_hp_lines": [["You have ", "5 HP", ". Each hit takes 1."], ["", "1 s", " of invincibility after a hit."]],
    "tuto_enemy_hp_lines": [["1 HP", "— fast patrollers"], ["2 HP", "— standard guards"], ["3 HP", "— heavy guardians"]],

    # Tutoriel : écholocalisation et textes
    "tuto_echo_intro": "The world is in total darkness.\nUse echo to reveal your surroundings.",
    "tuto_echo_radial_info": "Radial: 360°, 150 px, cd 2.5 s",
    "tuto_echo_dir_info": "Directional: ±25°, 300 px, cd 4 s  (unlockable)",
    "tuto_lost_souls_text": "On death, a soul appears\nwith all your money.\nAttack it to recover it —\nor dying again means permanent loss.",
    "tuto_progress_text": "Orb (in the world) → Double Jump.\nShop (sign, souls) → Dash (50 s),\ndir. echo (10 s), HP+ (20 s)...\n\nThe locked door requires the key.\nCheckpoints → auto-save.",
    "tuto_silence_text": "A hundred years ago, the \"Great Silence\"\nplunged the world into total and\npermanent darkness.\n\nCities became labyrinths\nteeming with creatures corrupted\nby the absence of light.",
    "tuto_gate_text": "At the heart of the ruins:\n\"The Gate of Dawn\".\n\nBehind it lies the First Light —\nthe only thing able to reverse the Silence.",
    "tuto_scout_text": "You master the Art of Echo —\na way of perceiving\nthe world through sound.\n\nWhere others see nothingness,\nyou hear outlines and dangers.",
    "tuto_wandering_text": "They are souls corrupted by\nthe Silence, trapped between two worlds.\n\nDefeating them frees their energy.",
    "tuto_cta_lines": ["Cross the ruins. Defeat the guardians.", "Find the key. Open the Gate.", "Bring back the light."],
}

# All the language dictionaries
LANGUAGES = {
    "fr": FR,
    "en": EN
}

# Currently selected language (default 'fr')
language_current = FR

def set_language(code_language="fr"):
    """Set the global language to use."""
    global language_current
    language_current = LANGUAGES.get(code_language, FR)

def get_text(key_item):
    """Look a text up by its key in the current language."""
    return language_current.get(key_item, key_item)