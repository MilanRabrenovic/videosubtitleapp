from app.services.subtitles import srt_timestamp_to_seconds, format_timestamp

def test():
    cases = [
        "00:00:01,000",
        "00:00:01.000", # dot
        "invalid",
        "",
        "None",
        None
    ]
    
    print("Testing srt_timestamp_to_seconds:")
    for c in cases:
        try:
            val = str(c) if c is not None else "None"
            # In editor.py we do str(b.get(...)) so let's simulate that
            if c is None:
                inp = "None"
            else:
                inp = str(c)
            
            res = srt_timestamp_to_seconds(inp)
            print(f"Input: {desc(c)} -> Result: {res}")
        except Exception as e:
            print(f"Input: {desc(c)} -> CRASH: {e}")

    print("\nTesting format_timestamp:")
    try:
        print(format_timestamp(1.5))
        print(format_timestamp(0))
        print(format_timestamp(-1))
    except Exception as e:
        print(f"CRASH: {e}")

def desc(v):
    if v is None: return "None"
    return f"'{v}'"

test()
