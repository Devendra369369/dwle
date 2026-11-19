import sys, unicodedata

def assigned(ranges):
    out = []
    for a, b in ranges:
        for cp in range(a, b + 1):
            ch = chr(cp)
            if unicodedata.name(ch, None):
                out.append(ch)
    return out

def build_tables():
    T = {}
    T[(8, 1)] = [chr(i) for i in range(128)]
    T[(8, 2)] = assigned([(0x0900, 0x097F)])
    T[(8, 3)] = assigned([(0x00A0, 0x00FF)]) + list("‘’“”–—…•₹€™")

    cons = [chr(c) for c in range(0x915, 0x93A) if c not in (0x929, 0x931, 0x934)]
    vir = chr(0x94D)
    for a, b in ((0x915, 0x937), (0x924, 0x930), (0x91C, 0x91E), (0x936, 0x930)):
        cons.append(chr(a) + vir + chr(b))
    forms = [""] + [chr(c) for c in (0x93E, 0x93F, 0x940, 0x941, 0x942,
                                      0x947, 0x948, 0x94B, 0x94C, 0x902, 0x903)]
    syl = [c + f for c in cons for f in forms]
    syl += [chr(c) for c in range(0x905, 0x915)]
    syl += [chr(c) for c in (0x93C, 0x902, 0x901, 0x903, 0x94D, 0x943,
                              0x949, 0x93D, 0x950, 0x964, 0x965)]
    syl += [chr(c) for c in range(0x966, 0x970)]
    T[(9, 1)] = syl

    emo = assigned([(0x1F1E6, 0x1F1FF), (0x1F300, 0x1F64F), (0x1F680, 0x1F6FF),
                    (0x1F900, 0x1F9FF), (0x1FA70, 0x1FAFF), (0x2600, 0x27BF)])
    emo += [chr(0x200D), chr(0xFE0F), chr(0x2B50), chr(0x2B55)]
    n = 10
    while 2 ** n - 11 < len(emo):
        n += 1
    T[(n, 1)] = emo

    zh = assigned([(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x20000, 0x2A6DF),
                   (0x2A700, 0x2B73F), (0x2B740, 0x2B81F), (0x2B820, 0x2CEAF),
                   (0x2CEB0, 0x2EBEF), (0x2EBF0, 0x2EE5D), (0x30000, 0x3134F),
                   (0x31350, 0x323AF), (0xF900, 0xFAFF), (0x3000, 0x303F),
                   (0x3040, 0x30FF), (0xFF00, 0xFFEF)])
    T[(17, 1)] = zh

    for k in T:
        T[k] = list(dict.fromkeys(T[k]))
        cap = 2 ** k[0] - 11
        if len(T[k]) > cap:
            raise ValueError("Table %s me %d chars, jagah sirf %d" % (k, len(T[k]), cap))
    return T, n

TABLES, EMOJI_W = build_tables()
INDEX = {k: {s: i + 1 for i, s in enumerate(v)} for k, v in TABLES.items()}
LOC = {}
for k, d in INDEX.items():
    for s, v in d.items():
        LOC.setdefault(s, []).append((k[0], k[1], v))
MAXLEN = 4

def encode(text):
    out = []
    st = {"w": 8, "lv": 1}

    def emit(code):
        out.append(format(code, "0%db" % st["w"]))

    def set_level(L):
        if L == st["lv"]:
            return
        s = str(L)
        if len(s) <= 2 or L > 2 ** st["w"] - 11:
            for d in s:
                emit(int(d) + 1)          # nested digit
        else:
            emit(1)                       # nested 0: agla code seedha level
            emit(L + 10)
        st["lv"] = L

    def set_window(nw):
        if nw == st["w"]:
            return
        emit(0)                           # null
        emit(nw + 10)                     # naya window
        st["w"] = nw

    i = 0
    while i < len(text):
        hit = None
        cur = INDEX.get((st["w"], st["lv"]), {})
        top = min(MAXLEN, len(text) - i)
        for L in range(top, 0, -1):       # pehle current table me
            seg = text[i:i + L]
            if seg in cur:
                hit = (st["w"], st["lv"], cur[seg], L)
                break
        if hit is None:
            for L in range(top, 0, -1):   # phir kahin bhi
                seg = text[i:i + L]
                if seg in LOC:
                    w, lv, v = LOC[seg][0]
                    hit = (w, lv, v, L)
                    break
        if hit is None:
            ch = text[i]
            raise ValueError("Table me nahi hai: %r (U+%04X)" % (ch, ord(ch)))
        w, lv, v, L = hit
        set_level(lv)                     # level pehle, purani window me
        set_window(w)
        emit(v + 10)
        i += L
    return "".join(out)

def decode(bits):
    w, level, i = 8, 1, 0
    out = []

    def read():
        nonlocal i
        if i + w > len(bits):
            return None
        c = int(bits[i:i + w], 2)
        i += w
        return c

    while True:
        c = read()
        if c is None:
            break
        if c == 0:                        # null -> window badlo
            d = read()
            if d is None:
                break
            if d < 11:
                raise ValueError("null ke baad window code chahiye")
            w = d - 10
        elif c == 1:                      # nested 0 -> ek code seedha level
            d = read()
            if d is None or d < 11:
                raise ValueError("nested 0 ke baad level code chahiye")
            level = d - 10
        elif c <= 10:                     # nested digits
            digits = [c - 1]
            while True:
                save = i
                n = read()
                if n is not None and 1 <= n <= 10:
                    digits.append(n - 1)
                else:
                    i = save
                    break
            level = int("".join(map(str, digits)))
        else:
            v = c - 10
            tab = TABLES.get((w, level))
            if tab is None or v > len(tab):
                raise ValueError("W%d L%d v%d table me nahi hai" % (w, level, v))
            out.append(tab[v - 1])
    return "".join(out)

def pack(bits):
    pad = bits + "0" * (-len(bits) % 8)
    data = int(pad, 2).to_bytes(len(pad) // 8, "big") if pad else b""
    return len(bits).to_bytes(4, "big") + data

def unpack(raw):
    n = int.from_bytes(raw[:4], "big")
    return "".join(format(b, "08b") for b in raw[4:])[:n]

def stats(text, bits):
    u8 = len(text.encode("utf-8")) * 8
    print("Characters:", len(text))
    print("Is scheme me bits:", len(bits))
    print("UTF-8 me bits:", u8)
    if u8:
        print("Bachat: %.1f%%" % (100 * (u8 - len(bits)) / u8))

def info():
    for k, v in TABLES.items():
        print("Window %2d Level %d : %6d chars (jagah %d)" % (k[0], k[1], len(v), 2 ** k[0] - 11))
    e = len(TABLES[(EMOJI_W, 1)])
    print("Emoji count: %d -> 2^%d = %d -> window %d" % (e, EMOJI_W, 2 ** EMOJI_W, EMOJI_W))

def test():
    samples = ["Hello, World!", "नमस्ते दुनिया", "क्षत्रिय ज्ञान कि की कू के कौ कं कः",
               "Hello 😀 🎉 world", "你好，世界 English", "Hi नमस्ते 你好 😀 ok ₹100",
               "A", "", "👨‍👩‍👧 🇮🇳"]
    ok = True
    for s in samples:
        bits = encode(s)
        back = decode(bits)
        res = "PASS" if back == s else "FAIL"
        if back != s:
            ok = False
        print(res, repr(s), len(bits), "bits")
    print("SAB PASS" if ok else "KUCH FAIL")

def main():
    a = sys.argv[1:]
    if not a or a[0] == "info":
        info()
    elif a[0] == "enc":
        bits = encode(a[1])
        print(bits)
        stats(a[1], bits)
    elif a[0] == "dec":
        print(decode(a[1]))
    elif a[0] == "encfile":
        text = open(a[1], encoding="utf-8").read()
        raw = pack(encode(text))
        open(a[2], "wb").write(raw)
        print("Likha:", a[2], len(raw), "bytes, original", len(text.encode("utf-8")), "bytes")
    elif a[0] == "decfile":
        text = decode(unpack(open(a[1], "rb").read()))
        open(a[2], "w", encoding="utf-8").write(text)
        print("Likha:", a[2])
    elif a[0] == "test":
        test()

main()
