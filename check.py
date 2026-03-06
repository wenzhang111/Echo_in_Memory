text = open('web_ui.html', encoding='utf-8').read()
for s in ['total-conversations', 'total-messages', 'avg-score', 'high-quality-ratio', 'topics-count', 'memory-list']:
    print(s, s in text)
