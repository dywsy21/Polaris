import re
map = r'E:\BaiduSyncdisk\Code Projects\PyQt Projects\Data Structure Project\backend\data\map_large'

s = set()
with open(map, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        reg = re.compile(r'<tag k="highway" v="(.*)"/>')
        match = reg.search(line)
        if match:
            s.add(match.group(1))
            # print(match.group(1), match.group(2))

with open('auxilary/output.txt', 'w', encoding='utf-8') as f:
    for item in s:
        f.write(item + '\n')