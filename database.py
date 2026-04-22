import sqlite3
import os
import hashlib


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class DatabaseManager:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(current_dir, "inventory.db")
        self._setup()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _column_exists(self, conn, table, column):
        c = conn.cursor()
        c.execute(f"PRAGMA table_info({table})")
        return any(row[1] == column for row in c.fetchall())

    def _table_exists(self, conn, table):
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        return c.fetchone() is not None

    def _setup(self):
        conn = self.get_connection()
        needs_migration = (
            not self._table_exists(conn, 'servers') or
            not self._column_exists(conn, 'servers', 'alias') or
            not self._column_exists(conn, 'servers', 'cpu_model') or
            not self._table_exists(conn, 'vms') or
            not self._column_exists(conn, 'vms', 'status') or
            not self._table_exists(conn, 'users')
        )
        conn.close()

        if needs_migration:
            print("Yeni şemaya geçiliyor...")
            conn2 = self.get_connection()
            c = conn2.cursor()
            c.execute('DROP TABLE IF EXISTS vms')
            c.execute('DROP TABLE IF EXISTS servers')
            conn2.commit()
            conn2.close()
            self._create_tables()
            self._seed_data()
        else:
            # Ensure users table and default admin exist even without full migration
            conn3 = self.get_connection()
            self._ensure_users(conn3)
            conn3.close()

    def _create_tables(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT UNIQUE NOT NULL,
                alias           TEXT,
                ip_address      TEXT,
                username        TEXT,
                password        TEXT,
                ram_gb          REAL,
                cpu_info        TEXT,
                notes           TEXT,
                type            TEXT DEFAULT 'Server',
                hostname        TEXT,
                cpu_model       TEXT,
                cpu_sockets     INTEGER,
                cpu_threads     INTEGER,
                total_ram       TEXT,
                system_disk     TEXT,
                swap            TEXT,
                kernel          TEXT,
                pve_version     TEXT,
                boot_mode       TEXT,
                storage_pools   TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS vms (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id       INTEGER,
                vm_id           INTEGER,
                name            TEXT NOT NULL,
                ip_address      TEXT,
                username        TEXT,
                password        TEXT,
                ram_gb          REAL,
                cores           INTEGER,
                disk_info       TEXT,
                notes           TEXT,
                status          TEXT,
                nic_info        TEXT,
                bios_type       TEXT,
                machine_type    TEXT,
                FOREIGN KEY (server_id) REFERENCES servers(id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT UNIQUE NOT NULL,
                password_hash   TEXT NOT NULL
            )
        ''')
        conn.commit()
        self._ensure_users(conn)
        conn.close()

    def _ensure_users(self, conn):
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)")
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                      ("admin", _hash_pw("atlas2024")))
        conn.commit()

    def authenticate(self, username: str, password: str) -> bool:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        row = c.fetchone()
        conn.close()
        if not row:
            return False
        return row['password_hash'] == _hash_pw(password)

    # ─── Seed Data ────────────────────────────────────────────────────────────

    def _seed_data(self):
        conn = self.get_connection()
        c = conn.cursor()

        servers_data = [
            # (name, alias, ip_address, username, password, type, notes,
            #  hostname, cpu_model, cpu_sockets, cpu_threads,
            #  total_ram, system_disk, swap, kernel, pve_version, boot_mode, storage_pools)
            ('10.10.1.249', 'Sunucu 1', '10.10.1.249:8006', 'root', 'o0gRJ4RSh9Q', 'Server', None,
             'Ostim', 'Intel(R) Xeon(R) Silver 4210 CPU @ 2.20GHz', 2, 40,
             '125.54 GiB', '93.99 GiB', '8.00 GiB',
             'Linux 5.4.73-1-pve', '6.3-2/22f57405', None,
             'local, local-zfs, QNAP, TNAS-OSTIM, TNAS01, asustor'),

            ('10.10.1.22', 'Sunucu 2', '10.10.1.22:8006', 'root', 'RCg3k83h4', 'Server', None,
             'ph08', 'Intel(R) Xeon(R) Gold 5320 CPU @ 2.20GHz', 2, 104,
             '503.52 GiB', '93.93 GiB', '16.00 GiB',
             'Linux 6.8.12-11-pve (2025-05-22)', '8.4.1/2a5fa54a8503f96d', 'EFI',
             'local, local-lvm, pve2, TNAS-SVR-Ph08, TNAS01'),

            ('10.10.1.247', 'Sunucu 3', '10.10.1.247:8006', 'root', 'Ba5j8ILEvRo', 'Server', None,
             'pve', 'Intel(R) Xeon(R) CPU E5-2450 0 @ 2.10GHz', 2, 32,
             '94.33 GiB', '1.63 TiB', 'N/A',
             'Linux 6.2.16-4-pve #1 SMP (2023-07-14)', '8.0.3/bbf3993334bfa916', None,
             'local, local-zfs, TNAS01, Tnas-H15'),

            ('10.10.1.180', 'Sunucu 4', '10.10.1.180:8006', 'root', 'CXlfZKf6PiQ', 'Server', None,
             'h11', 'Intel(R) Xeon(R) Gold 5218R CPU @ 2.10GHz', 2, 80,
             '220.05 GiB', '93.93 GiB', '8.00 GiB',
             'Linux 5.15.74-1-pve #1 (2022-11-14)', '7.3-3/c3928077', None,
             'local, TNAS-H11, TNAS01, asustor'),

            ('10.10.1.206', 'Sunucu 5 (h15)', '10.10.1.206:8006', 'root', 'wCQrN$7G4g', 'Server', None,
             'h15', 'Intel(R) Xeon(R) Gold 5218R CPU @ 2.10GHz', 2, 80,
             '251.53 GiB', '93.93 GiB', '8.00 GiB',
             'Linux 6.5.11-4-pve (2023-11-20)', '8.1.3/b46aac3b42da5d15', 'EFI',
             'local, local-lvm, yedek, TNAS-SRVH15, TNAS01'),

            ('10.10.1.252', 'Sunucu 6', '10.10.1.252:8006', 'root', '@stim@06.', 'Server', None,
             'ph08', 'Intel(R) Xeon(R) Silver 4114 CPU @ 2.20GHz', 2, 40,
             '125.18 GiB', '93.93 GiB', '8.00 GiB',
             'Linux 6.8.4-2-pve (2024-04-10)', '8.2.2/9355359cd7afbae4', 'EFI',
             'local, local-lvm, TNAS-SRV-PH08-252, TNAS01'),

            ('10.10.1.176', 'Sunucu 7', '10.10.1.176:8006', 'root', '!byd1570!', 'Server', None,
             'ph07', 'Intel(R) Xeon(R) Platinum 8173M CPU @ 2.00GHz', 2, 112,
             '503.24 GiB', '93.93 GiB', '8.00 GiB',
             'Linux 6.8.4-2-pve (2024-04-10)', '8.2.2/9355359cd7afbae4', 'EFI',
             'local, local-lvm, TNAS-SRVPH07, TNAS01, ds418c'),

            ('10.10.1.246', 'Sunucu 8', '10.10.1.246:8006', 'Administrator', 'Ostim123', 'Server', 'Windows tabanlı — ekran görüntüsü alınamadı',
             None, None, None, None, None, None, None, None, None, None, None),

            ('10.10.1.220', 'QNAP NAS', '10.10.1.220', None, None, 'Storage', 'Giriş bilgisi bulunamadı',
             None, None, None, None, None, None, None, None, None, None, None),

            ('10.10.1.118', 'Terramaster NAS', '10.10.1.118', 'TnasOstim', 'Ostim1453.', 'Storage', None,
             None, None, None, None, None, None, None, None, None, None, None),

            ('10.10.1.221', 'Asus NAS', '10.10.1.221', None, None, 'Storage', 'Giriş bilgisi bulunamadı',
             None, None, None, None, None, None, None, None, None, None, None),

            ('10.10.1.218', 'ZyXEL NAS', '10.10.1.218', None, None, 'Storage', 'Giriş yapılamıyor',
             None, None, None, None, None, None, None, None, None, None, None),

            ('10.10.1.219', 'DS414 NAS', '10.10.1.219', 'admin', '06bm1220', 'Storage', None,
             None, None, None, None, None, None, None, None, None, None, None),

            ('10.10.1.240', 'AS1004T NAS', '10.10.1.240', None, None, 'Storage', 'Giriş bilgisi bulunamadı',
             None, None, None, None, None, None, None, None, None, None, None),
        ]

        s_map = {}
        for s in servers_data:
            c.execute('''INSERT OR IGNORE INTO servers
                (name, alias, ip_address, username, password, type, notes,
                 hostname, cpu_model, cpu_sockets, cpu_threads,
                 total_ram, system_disk, swap, kernel, pve_version, boot_mode, storage_pools)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', s)
            c.execute('SELECT id FROM servers WHERE name = ?', (s[0],))
            row = c.fetchone()
            if row:
                s_map[s[1]] = row['id']

        # (server_alias, vm_id, name, ram_gb, cores, disk_info, notes, status, nic_info, bios_type, machine_type)
        vms_data = [
            # ── Sunucu 1 ──────────────────────────────────────────────────────
            ('Sunucu 1', 1103, 'owncloud',               None, None, None,              'Kapatıldı 09:38', 'stopped', None, None, None),
            ('Sunucu 1', 4416, 'glpi',                   4,    2,    '32G local-lvm',   'Kapatıldı 09:40', 'running', 'virtio BC:24:11:F0:4F:7E, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 1', 3346, 'srv-basvuru-portal',     12,   6,    '100G local-lvm',  'Kapatıldı 09:43', 'running', 'virtio D6:C6:0F:D7:AC:5F, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 1', 1455, 'mezunplatformu',         2,    2,    '64G local-lvm',   'Kapatıldı 09:44', 'running', 'virtio 26:EA:FD:BE:1A:6C, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 1', 1207, 'kohanew',                16,   8,    '250G local-lvm',  "Proxmox'tan zorla kapandı", 'running', 'virtio 3E:D5:2C:27:6C:9A, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 1', 111,  'yetkim-clone-12-02-2026', 8,  8,    '50G QNAP (qcow2)','Kapatıldı 09:53', 'running', 'virtio 36:48:30:38:80:CA, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 1', 108,  'dspace9-backup11112025', 6,   16,   '100G QNAP (qcow2)','Kapatıldı 09:54', 'stopped', 'virtio 16:21:88:82:A7:63, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 1', 104,  'back-dspace-91125',      16,  8,    '120G local-lvm',  'Kapatıldı 09:55', 'running', 'virtio B2:70:8F:94:97:44, vmbr0', 'SeaBIOS', 'i440fx'),
            # ── Sunucu 2 ──────────────────────────────────────────────────────
            ('Sunucu 2', 9946, 'nps-server',             4,   2,    '40G pve2',         'Kapatıldı 10:06', 'running', 'virtio, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 2', 3045, 'OSTIM-EBYS-DB',          None,None, None,               'Kapatıldı 10:07, Aktif değil', 'stopped', None, None, None),
            ('Sunucu 2', 3046, 'OSTIM-EBYS-DB-2',        None,None, None,               'Kapatıldı 10:07, Aktif değil', 'stopped', None, None, None),
            ('Sunucu 2', 2022, 'Pr-StokTakip',           4,   4,    '50G local-lvm',    'Kapatıldı 10:09', 'running', 'virtio BC:24:11:A9:84:15, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 2', 203,  'odeme-web16-test',       10,  4,    '50G pve2',         'Kapatıldı', 'running', 'virtio BC:24:11:EF:3F:E6, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 2', 202,  'odeme-web16',            50,  16,   '50G local-lvm',    'Kapatıldı', 'running', 'virtio BC:24:11:3B:14:A2, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 2', 201,  'keycloak',               32,  8,    '30G local-lvm',    'Kapatıldı', 'running', 'virtio 6A:38:1F:58:BB:C8, vmbr0', 'SeaBIOS', 'i440fx'),
            ('Sunucu 2', 2809, 'sP-muh-ubuntu',          20,  8,    '100G local-lvm',   None, 'running', 'virtio, vmbr0', 'SeaBIOS', 'pc-i440fx-8.0'),
            ('Sunucu 2', 2203, 'ebysapp',                64,  32,   '1290G pve2',       None, 'running', 'virtio, vmbr0', 'SeaBIOS', 'pc-i440fx-8.0'),
            ('Sunucu 2', 2201, 'ebysdb',                 64,  16,   '860G pve2',        None, 'running', 'virtio, vmbr0', 'SeaBIOS', 'pc-i440fx-8.0'),
            ('Sunucu 2', 100,  'otusem',                 12,  32,   '500G pve2',        None, 'running', 'virtio CE:A7:95:27:47:13, vmbr0', 'SeaBIOS', 'pc-i440fx-8.0'),
            # ── Sunucu 3 ──────────────────────────────────────────────────────
            ('Sunucu 3', 108,  'ollama',                 None, None, None,              None, None, None, None, None),
            ('Sunucu 3', 106,  'yetkim2.0.7',            8,   4,    '100G local (qcow2)', None, 'running', None, None, None),
            ('Sunucu 3', 104,  'GitLabTest',             8,   6,    '32G local-zfs',    None, 'running', None, 'SeaBIOS', None),
            ('Sunucu 3', 102,  'OtuPerformans',          8,   4,    '200G local-zfs',   None, 'running', None, 'SeaBIOS', None),
            # ── Sunucu 4 ──────────────────────────────────────────────────────
            ('Sunucu 4', 100,  'istakip',                16,  32,   '32G local-lvm',    None, 'running', None, None, None),
            ('Sunucu 4', 102,  'kapi',                   4,   4,    '20G local-lvm',    None, 'running', None, None, None),
            ('Sunucu 4', 106,  'surec',                  8,   4,    '32G local-lvm',    None, 'running', None, None, None),
            ('Sunucu 4', 0,    'sP-Proxmox-Management', None, None, None,              None, None, None, None, None),
            ('Sunucu 4', 162,  'lmsclus',                4,   4,    '35G local-lvm',    None, 'running', None, None, None),
            ('Sunucu 4', 166,  'mStore3',                8,   4,    '685G local-lvm',   None, 'running', None, None, None),
            ('Sunucu 4', 167,  'psql',                   16,  8,    '535G local-lvm',   None, 'running', None, None, None),
            ('Sunucu 4', 168,  'redis',                  4,   4,    '35G local-lvm',    None, 'running', None, None, None),
            ('Sunucu 4', 169,  'mood1',                  16,  8,    '35G local-lvm',    None, 'running', None, None, None),
            ('Sunucu 4', 170,  'mood2',                  16,  4,    '35G local-lvm',    None, 'running', None, None, None),
            ('Sunucu 4', 175,  'UniTime',                4,   4,    '35G local-lvm',    None, 'running', None, None, None),
            # ── Sunucu 5 h15 ──────────────────────────────────────────────────
            ('Sunucu 5 (h15)', 100,  'github',              32,  8,  '60G local-lvm',   None, 'running', None, None, None),
            ('Sunucu 5 (h15)', 110,  'dotnetweb',           40,  16, '250G local-lvm',  'Windows Server 2019', 'running', None, None, None),
            ('Sunucu 5 (h15)', 111,  'Odootest',            8,   8,  '32G local-lvm',   None, 'running', None, None, None),
            ('Sunucu 5 (h15)', 112,  'web16test',           32,  8,  '100G local-lvm',  None, 'running', None, None, None),
            ('Sunucu 5 (h15)', 113,  'Portal',              32,  8,  '100G local-lvm',  None, 'running', None, None, None),
            ('Sunucu 5 (h15)', 114,  'Kafka',               4,   4,  '15G local-lvm',   None, 'running', None, None, None),
            ('Sunucu 5 (h15)', 201,  'high-availability-1', None, None, None,           'Murat - tünel sorulacak', None, None, None, None),
            ('Sunucu 5 (h15)', 202,  'high-availability-2', None, None, None,           'Murat - tünel sorulacak', None, None, None, None),
            ('Sunucu 5 (h15)', 203,  'high-availability-3', None, None, None,           'Murat - tünel sorulacak', None, None, None, None),
            ('Sunucu 5 (h15)', 204,  'high-availability-4', None, None, None,           'Murat - tünel sorulacak', None, None, None, None),
            ('Sunucu 5 (h15)', 1107, 'tto-basvuru-formu3',  8,   4,  '50G local-lvm',   None, 'stopped', None, None, None),
            ('Sunucu 5 (h15)', 108,  'Web16Prod',           96,  32, '100G local-lvm',  None, 'running', None, None, None),
            # ── Sunucu 6 ──────────────────────────────────────────────────────
            ('Sunucu 6', 100,  'zabbix',              32,  16, '100G local-lvm',        None, 'running', None, None, None),
            ('Sunucu 6', 101,  'pfsense',             16,  8,  '100G local-lvm',        None, 'running', None, None, None),
            ('Sunucu 6', 102,  'ERA-NET',             8,   8,  '50G local-lvm',         None, 'running', None, None, None),
            ('Sunucu 6', 108,  'test-wfe',            8,   4,  None,                    'Açılmayacak', 'running', None, None, None),
            ('Sunucu 6', 5525, 'proxus-server',       16,  8,  '100G local-lvm',        None, 'running', None, None, None),
            ('Sunucu 6', 107,  'ytkmserver',          16,  8,  '100G local-lvm',        None, 'running', None, None, None),
            ('Sunucu 6', 5528, 'pro-ebys-izin-likom', 8,   4,  '32G local-lvm',        None, 'running', None, None, None),
            ('Sunucu 6', 6642, 'srv-proxy-wireGuard', 4,   2,  '90G local-lvm',         None, 'running', None, None, None),
            # ── Sunucu 7 ──────────────────────────────────────────────────────
            ('Sunucu 7', 100,  'bkys-app',           32,  4,  '250G local-lvm',         None, 'running', None, None, None),
            ('Sunucu 7', 101,  'bkys-db',            32,  4,  '250G local-lvm',         None, 'running', None, None, None),
            ('Sunucu 7', 103,  'ZABBIX',             16,  9,  '500G local-lvm',         None, 'running', None, None, None),
            ('Sunucu 7', 105,  'RUIJI-NAC',          32,  4,  '200G local-lvm',         None, 'running', None, None, None),
            ('Sunucu 7', 1044, 'hpcc1',              8,   2,  '32G local-lvm',          None, 'running', None, None, None),
            ('Sunucu 7', 1045, 'hpcc2',              8,   2,  '32G local-lvm',          None, 'stopped', None, None, None),
            ('Sunucu 7', 1046, 'ostimChatbot',       16,  8,  '32G local-lvm',          None, 'running', None, None, None),
            ('Sunucu 7', 3518, 'xabbix-netpanel',    10,  4,  '102G local-lvm',         None, 'stopped', None, None, None),
            ('Sunucu 7', 2101, 'prolizapp',          96,  32, '300G local-lvm',          None, 'running', None, None, None),
            ('Sunucu 7', 2103, 'prolizdb',           64,  16, '300G local-lvm',          None, 'running', None, None, None),
        ]

        for v in vms_data:
            alias = v[0]
            if alias in s_map:
                c.execute('''INSERT INTO vms
                    (server_id, vm_id, name, ram_gb, cores, disk_info, notes, status, nic_info, bios_type, machine_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (s_map[alias], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8], v[9], v[10]))

        conn.commit()
        conn.close()
        print("Veritabanı hazırlandı.")

    # ─── Read ─────────────────────────────────────────────────────────────────

    def get_inventory(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM servers ORDER BY type DESC, alias')
        servers = [dict(row) for row in c.fetchall()]
        c.execute('SELECT * FROM vms ORDER BY server_id, vm_id')
        vms = [dict(row) for row in c.fetchall()]
        conn.close()
        for server in servers:
            server['vms'] = [vm for vm in vms if vm['server_id'] == server['id']]
        return servers

    def get_server(self, server_id: int):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM servers WHERE id=?', (server_id,))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_vm(self, vm_id: int):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM vms WHERE id=?', (vm_id,))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    # ─── Create ───────────────────────────────────────────────────────────────

    def add_server(self, data: dict) -> int:
        conn = self.get_connection()
        c = conn.cursor()
        fields = ['name', 'alias', 'ip_address', 'username', 'password', 'type', 'notes',
                  'hostname', 'cpu_model', 'cpu_sockets', 'cpu_threads',
                  'total_ram', 'system_disk', 'swap', 'kernel', 'pve_version', 'boot_mode', 'storage_pools']
        vals = [data.get(f) for f in fields]
        placeholders = ','.join(['?'] * len(fields))
        col_names = ','.join(fields)
        c.execute(f'INSERT INTO servers ({col_names}) VALUES ({placeholders})', vals)
        new_id = c.lastrowid
        conn.commit()
        conn.close()
        return new_id

    def add_vm(self, data: dict) -> int:
        conn = self.get_connection()
        c = conn.cursor()
        fields = ['server_id', 'vm_id', 'name', 'ip_address', 'username', 'password',
                  'ram_gb', 'cores', 'disk_info', 'notes', 'status', 'nic_info', 'bios_type', 'machine_type']
        vals = [data.get(f) for f in fields]
        placeholders = ','.join(['?'] * len(fields))
        col_names = ','.join(fields)
        c.execute(f'INSERT INTO vms ({col_names}) VALUES ({placeholders})', vals)
        new_id = c.lastrowid
        conn.commit()
        conn.close()
        return new_id

    # ─── Update ───────────────────────────────────────────────────────────────

    def update_server(self, server_id: int, data: dict):
        conn = self.get_connection()
        c = conn.cursor()
        fields = ['name', 'alias', 'ip_address', 'username', 'password', 'type', 'notes',
                  'hostname', 'cpu_model', 'cpu_sockets', 'cpu_threads',
                  'total_ram', 'system_disk', 'swap', 'kernel', 'pve_version', 'boot_mode', 'storage_pools']
        set_clause = ', '.join(f'{f}=?' for f in fields)
        vals = [data.get(f) for f in fields] + [server_id]
        c.execute(f'UPDATE servers SET {set_clause} WHERE id=?', vals)
        conn.commit()
        conn.close()

    def update_vm(self, vm_db_id: int, data: dict):
        conn = self.get_connection()
        c = conn.cursor()
        fields = ['server_id', 'vm_id', 'name', 'ip_address', 'username', 'password',
                  'ram_gb', 'cores', 'disk_info', 'notes', 'status', 'nic_info', 'bios_type', 'machine_type']
        set_clause = ', '.join(f'{f}=?' for f in fields)
        vals = [data.get(f) for f in fields] + [vm_db_id]
        c.execute(f'UPDATE vms SET {set_clause} WHERE id=?', vals)
        conn.commit()
        conn.close()

    # ─── Delete ───────────────────────────────────────────────────────────────

    def delete_server(self, server_id: int):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('DELETE FROM vms WHERE server_id=?', (server_id,))
        c.execute('DELETE FROM servers WHERE id=?', (server_id,))
        conn.commit()
        conn.close()

    def delete_vm(self, vm_db_id: int):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('DELETE FROM vms WHERE id=?', (vm_db_id,))
        conn.commit()
        conn.close()


db_manager = DatabaseManager()
