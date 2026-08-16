from bs4 import BeautifulSoup

def check():
    with open('dashboard/templates/index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')
    modals = soup.find_all(class_='modal-overlay')
    print(f'Total modal-overlay found: {len(modals)}')
    for m in modals:
        parent = m.parent.name if m.parent else 'None'
        parent_id = m.parent.get('id') if m.parent else ''
        parent_cls = m.parent.get('class') if m.parent else ''
        print(f'Modal id={m.get("id")} -> Parent: <{parent} id="{parent_id}" class="{parent_cls}">')

if __name__ == "__main__":
    check()
