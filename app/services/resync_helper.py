from typing import List, Dict, Any


def parse_timestamp(ts: str) -> float:
    try:
        ts = ts.replace(",", ".")
        parts = ts.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return 0.0
    except (ValueError, IndexError):
        return 0.0


def fill_subtitle_gaps(subtitles: List[Dict[str, Any]], max_gap: float = 5.0) -> List[Dict[str, Any]]:
    """
    Return a COPY of subtitles with small gaps filled for seamless playback.
    """
    import copy
    if not subtitles:
        return []

    export_subs = copy.deepcopy(subtitles)
    export_subs.sort(key=lambda b: parse_timestamp(str(b.get("start", "00:00:00,000"))))
    
    for i in range(len(export_subs) - 1):
        curr = export_subs[i]
        next_b = export_subs[i+1]
        
        curr_end = parse_timestamp(str(curr.get("end", "00:00:00,000")))
        next_start = parse_timestamp(str(next_b.get("start", "00:00:00,000")))
        
        gap = next_start - curr_end
        if 0 < gap < max_gap:
             curr["end"] = next_b.get("start")
             
    return export_subs


def resync_words_to_blocks(words: List[Dict[str, Any]], blocks: List[Dict[str, Any]]) -> None:
    """
    Update 'words' timestamps to match 'blocks' by sequentially aligning text.
    This handles cases where blocks are moved/dragged on the timeline, decoupling
    them from the original word timestamps.
    """
    import re


    def normalize(s: str) -> str:
        return re.sub(r"\W+", "", s.lower())

    if not words or not blocks:
        return

    word_cursor = 0
    total_words = len(words)
    
    for block in blocks:
        block_text = str(block.get("text", ""))
        block_start = parse_timestamp(str(block.get("start", "00:00:00,000")))
        block_end = parse_timestamp(str(block.get("end", "00:00:00,000")))
        
        # Tokenize block text roughly the same way words are
        # This is a heuristic. Ideally we use the same tokenizer as transcription.
        # But 'words' are already tokens.
        # We need to find a sequence of words that matches block_text.
        
        # Simple tokenization by splitting
        block_tokens_raw = block_text.split()
        block_tokens_norm = [normalize(t) for t in block_tokens_raw if normalize(t)]
        
        if not block_tokens_norm:
            continue
            
        # Search for this sequence in words starting at word_cursor
        # We look ahead a bit to handle potential skipped/deleted words between blocks.
        # But we don't look ahead infinitely.
        
        match_start_idx = -1
        match_end_idx = -1
        
        # Look ahead up to 50 words? Or unlimited?
        # If the user deleted a huge chunk, we need to skip it.
        # So unlimited lookahead is likely safer, but we should prioritize first match.
        
        search_limit = min(total_words, word_cursor + 500) 
        
        for i in range(word_cursor, search_limit):
            # Check if words[i] matches block_tokens_norm[0]
            if i >= total_words: break
            
            w_norm = normalize(str(words[i].get("word", "") or words[i].get("text", "")))
            if w_norm == block_tokens_norm[0]:
                # Potential match start. Check subsequent.
                match = True
                current_match_end = i
                
                # Verify rest of sequence
                b_idx = 1
                w_idx = i + 1
                while b_idx < len(block_tokens_norm):
                    if w_idx >= total_words:
                        match = False
                        break
                    
                    next_w_norm = normalize(str(words[w_idx].get("word", "") or words[w_idx].get("text", "")))
                    if next_w_norm == block_tokens_norm[b_idx]:
                        current_match_end = w_idx
                        b_idx += 1
                        w_idx += 1
                    else:
                        match = False
                        break
                
                if match:
                    match_start_idx = i
                    match_end_idx = current_match_end
                    break
        
        if match_start_idx != -1:
            # Update timestamps for matched words
            matched_words = words[match_start_idx : match_end_idx + 1]
            count = len(matched_words)
            
            # Simple linear interpolation of time
            # We preserve relative durations if possible?
            # Or just stretch?
            # Stretching is safer to ensure they fit in the block.
            
            duration = max(0.01, block_end - block_start)
            
            # Use original relative offsets?
            # If we just drag, the relative spacing is preserved.
            # But absolute times are wrong.
            # We should calculate the shift amount based on the first word?
            # But the user might have resized the block (stretch).
            
            # Let's use proportional scaling.
            orig_start = float(matched_words[0].get("start", 0.0))
            orig_end = float(matched_words[-1].get("end", 0.0))
            orig_duration = max(0.01, orig_end - orig_start)
            
            scale = duration / orig_duration
            
            for w in matched_words:
                w_s = float(w.get("start", 0.0))
                w_e = float(w.get("end", 0.0))
                
                rel_s = w_s - orig_start
                rel_e = w_e - orig_start
                
                new_s = block_start + (rel_s * scale)
                new_e = block_start + (rel_e * scale)
                
                w["start"] = new_s
                w["end"] = new_e
            
            word_cursor = match_end_idx + 1
