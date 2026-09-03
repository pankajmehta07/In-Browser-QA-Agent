import re

def rule_based_parser(instruction:str) -> list:
    steps = []

    # split by period or new line
    sentences = re.split(r'[.\n]+', instruction)

    for sentence in sentences:
        sentence = sentence.strip().lower()

        if not sentence:
            continue

        # goto pattern: "go to X" or "navigate to X"
        goto = re.match(r"(?:go\s+to|navigate\s+to|open)\s+(.+)", sentence)
        if goto:
            steps.append({"action":"goto", "target":goto.group(1).strip().title()})
            continue
        
        # type pattern: "type X into Y"
        type_match = re.match(r"type\s+(.+?)\s+into\s+(.+)", sentence)
        if type_match:
            steps.append({
                "action":"type", 
                "target":type_match.group(2).strip().title(),
                "value":type_match.group(1).strip().title(),
                })
            continue

        # click pattern: "click X"
        click = re.match(r"click\s+(.+)", sentence)
        if click:
            steps.append({"action":"click", "target":click.group(1).strip().title()})
            continue

        # check visible: "check X is visible"
        check_vis = re.match(r"check\s+(.+?)\s+is\s+visible", sentence)
        if check_vis:
            steps.append({"action":"check_visible", "target":check_vis.group(1).strip().title()})
            continue

        # check contains: "check X contains Y"
        check_contains = re.match(r"check\s+(.+?)\s+contains\s+(.+)", sentence)
        if check_contains:
            steps.append({
                "action":"check_contains", 
                "target":check_contains.group(1).strip().title(),
                "value":check_contains.group(2).strip().title(),
                })
            continue
    return steps
        


if __name__=="__main__":
    rule_based_parser("GO TO link.com")
