#!/usr/bin/env python
with open('src/infra/db/repositories.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Add a new method to PgTasksRepo for conditional UPDATE with RETURNING
new_method = \"\"\"

    def update_event_seq(
        self,
        task_id: uuid.UUID,
        new_event_seq: int,
        expected_status: str,
    ) -> bool:
        \"\"\"Conditional UPDATE with RETURNING event_seq.
        
        UPDATE tasks SET event_seq = %s WHERE task_id = %s AND status = %s
        RETURNING event_seq.
        \"\"\"
        with get_domain_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    \"\"\"UPDATE tasks SET event_seq = %s WHERE task_id = %s AND status = %s RETURNING event_seq\"\"\",
                    (new_event_seq, str(task_id), expected_status),
                )
                row = cur.fetchone()
                return bool(row) and row[0] == new_event_seq
\"\"\"

# Insert after update_heartbeat method
if 'def update_heartbeat' in content and 'def update_event_seq' not in content:
    lines = content.split('\n')
    new_lines = []
    i = 0
    added = False
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        if 'def update_heartbeat' in line and not added:
            # Find the end of the method (next def or end of class)
            j = i + 1
            while j < len(lines) and not (lines[j].startswith('def ') or lines[j].startswith('class ')):
                j += 1
            # Insert the new method before the found def/class
            insert_pos = j - 1  # position before the next method/class
            # Reverse pop to insert at the right position
            # Actually, let's just insert after the update_heartbeat block
            # by counting the lines properly
            added = True
            # Insert the new method after line j-1
            # We need to insert at position j (after the last line of update_heartbat)
            # Let's just append the new method after the current position
            new_lines.append(new_method.strip())
        i += 1
    content = '\n'.join(new_lines)
    with open('src/infra/db/repositories.py', 'w', encoding='utf-8', errors='replace') as f:
        f.write(content)
    print('Added update_event_seq method')
else:
    print('Method already exists or update_heartbeat not found')