from __future__ import annotations

import html
import sys


def main(ws_file: str, orders_file: str, out_file: str):
    ws = open(ws_file, encoding='utf-8').read()[:20000]
    od = open(orders_file, encoding='utf-8').read()[:20000]
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write('<html><body><h1>Load Test Report</h1>')
        f.write('<h2>WebSocket</h2><pre>' + html.escape(ws) + '</pre>')
        f.write('<h2>Orders</h2><pre>' + html.escape(od) + '</pre>')
        f.write('</body></html>')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
