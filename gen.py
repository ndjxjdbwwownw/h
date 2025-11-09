import requests, re, subprocess, os, urllib3, datetime, threading, time, sys, sqlite3
from bs4 import BeautifulSoup
from colorama import Fore, Back, Style, init
from pathvalidate import sanitize_filename

# Initialize colorama for cross-platform colored output
init(autoreset=True)

e = datetime.datetime.now()
current_date = e.strftime("%Y-%m-%d-%H-%M-%S")
urllib3.disable_warnings()
agent = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}
pages = 0
scraped = 0
db_lock = threading.Lock()  # Database lock for thread safety

# Statistics tracking
site_stats = {
    'nohide.space': {'posts': 0, 'combos': 0, 'status': 'Waiting'},
    'crackingx.com': {'posts': 0, 'combos': 0, 'status': 'Waiting'},
    'combolist.xyz': {'posts': 0, 'combos': 0, 'status': 'Waiting'},
    'sendspace.com': {'posts': 0, 'combos': 0, 'status': 'Waiting'},
    'gofile.io': {'posts': 0, 'combos': 0, 'status': 'Waiting'},
    'mediafire.com': {'posts': 0, 'combos': 0, 'status': 'Waiting'},
    'pixeldrain.com': {'posts': 0, 'combos': 0, 'status': 'Waiting'}
}

stats_lock = threading.Lock()
display_running = True
start_time = None

# Database setup
def init_database():
    """Initialize the SQLite database and create the table if it doesn't exist"""
    with db_lock:
        conn = sqlite3.connect('pulled.db', timeout=30.0)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS combos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                pass TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(email, pass)
            )
        ''')
        # Create index for faster duplicate checking
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_pass ON combos(email, pass)')
        conn.commit()
        conn.close()

def save_to_database(email, password):
    """Save email:password combo to database, avoiding duplicates"""
    try:
        with db_lock:
            conn = sqlite3.connect('pulled.db', timeout=30.0)
            cursor = conn.cursor()
            
            # Check if combo already exists
            cursor.execute('SELECT 1 FROM combos WHERE email = ? AND pass = ? LIMIT 1', (email, password))
            if cursor.fetchone() is None:
                # Combo doesn't exist, insert it
                cursor.execute('INSERT INTO combos (email, pass) VALUES (?, ?)', (email, password))
                conn.commit()
                conn.close()
                return True  # Successfully added
            else:
                conn.close()
                return False  # Duplicate, not added
    except Exception as e:
        return False  # Error occurred

def save_batch_to_database(combos_list):
    """Save multiple combos to database in batch, avoiding duplicates"""
    if not combos_list:
        return 0
    
    added_count = 0
    try:
        with db_lock:
            conn = sqlite3.connect('pulled.db', timeout=30.0)
            cursor = conn.cursor()
            
            for email, password in combos_list:
                # Check if combo already exists
                cursor.execute('SELECT 1 FROM combos WHERE email = ? AND pass = ? LIMIT 1', (email, password))
                if cursor.fetchone() is None:
                    # Combo doesn't exist, insert it
                    cursor.execute('INSERT INTO combos (email, pass) VALUES (?, ?)', (email, password))
                    added_count += 1
            
            conn.commit()
            conn.close()
            return added_count
    except Exception as e:
        return 0
 
class leech():
    def save(output, thread, host, alr = False):
        global scraped
        if alr == False: filtered = [line.strip() for line in output.split('\n') if re.compile(r'([^\s|]+[@][^\s|]+[.][^\s|]+[:][^\s|]+)').match(line.strip()) and len(line.strip()) <= 64 and line.strip()]
        else: filtered = output
        filtered = [f"{line.split(':')[-2]}:{line.split(':')[-1]}" if line.startswith("http") else line for line in filtered]
        scraped += len(filtered)
        
        # Update site statistics
        with stats_lock:
            for site in site_stats:
                if site in host:
                    site_stats[site]['combos'] += len(filtered)
                    break
        
        # Save to database in batch
        combos_to_save = []
        for combo in filtered:
            if ':' in combo:
                parts = combo.split(':', 1)  # Split only on first colon
                if len(parts) == 2:
                    email, password = parts
                    combos_to_save.append((email, password))
        
        if combos_to_save:
            save_batch_to_database(combos_to_save)
    def gofile(link, thread, content_id = None):
        if content_id is not None:
            token = requests.post("https://api.gofile.io/accounts").json()["data"]["token"]
            wt = requests.get("https://gofile.io/dist/js/alljs.js").text.split('wt: "')[1].split('"')[0]
            data = requests.get(f"https://api.gofile.io/contents/{content_id}?wt={wt}&cache=true", headers={"Authorization": "Bearer " + token},).json()
            if data["status"] == "ok":
                if data["data"].get("passwordStatus", "passwordOk") == "passwordOk":
                    dir = os.path.join(link, sanitize_filename(data["data"]["name"]))
                    if data["data"]["type"] == "folder":
                        for children_id in data["data"]["childrenIds"]:
                            if data["data"]["children"][children_id]["type"] == "folder":
                                leech.gofile(dir, thread, content_id=children_id)
                            else:
                                link = data["data"]["children"][children_id]["link"]
                                leech.save(requests.get(link, headers={"Cookie": "accountToken=" + token}).text, thread, "gofile.io")
                    else:
                        link = data["data"]["link"]
                        leech.save(requests.get(link, headers={"Cookie": "accountToken=" + token}).text, thread, "gofile.io")
        else: leech.gofile(link, thread, link.split("/")[-1])
    def handle(link, thread):
        try:
            if link.startswith('https://www.upload.ee/files/'):
                f = BeautifulSoup(requests.get(link, headers=agent).text, 'html.parser')
                download = f.find('a', id='d_l').get('href')
                leech.save(requests.get(download, headers=agent).text, thread, "upload.ee")
            elif link.startswith('https://www.mediafire.com/file/'):
                f = BeautifulSoup(requests.get(link, headers=agent).text, 'html.parser')
                download = f.find('a', id='downloadButton').get('href')
                leech.save(requests.get(download, headers=agent).text, thread, "mediafire.com")
            elif link.startswith('https://pixeldrain.com/u/'):
                leech.save(requests.get(link.replace("/u/", "/api/file/")+"?download", headers=agent).text, thread, "pixeldrain.com")
            elif link.startswith('https://mega.nz/file/'):
                process = subprocess.Popen(f"megatools\\megatools.exe dl {link} --no-ask-password --print-names", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True,)
                output = process.stdout.readlines()
                process.wait()
                saved = output[-1].strip()
                leech.save(open(saved, 'r', encoding='utf-8').read(), thread, "mega.nz")
                os.remove(saved)
            elif link.startswith('https://www.sendspace.com/file/'):
                req = requests.get(link, headers=agent)
                soup = BeautifulSoup(req.text, 'html.parser')
                download_link = soup.find('a', {'id': 'download_button'})
                link = download_link['href']
                leech.save(requests.get(link, verify=False, headers=agent).text, thread, "sendspace.com")
            elif link.startswith('https://gofile.io/d/'):
                leech.gofile(link, thread)
            #else: print(f"Unknown paste site: {link}")
        except: pass

    def nohide():
        dupe = []
        with stats_lock:
            site_stats['nohide.space']['status'] = 'Running'
        try:
            for page in range(1, pages):
                req = requests.get(f"https://nohide.space/forums/free-email-pass.3/page-{page}?order=post_date&direction=desc", headers=agent)
                soup = BeautifulSoup(req.text, 'html.parser')
                target_div = soup.find('div', class_='structItemContainer-group js-threadList')
                if target_div:
                    links = target_div.find_all('a')
                    with stats_lock:
                        site_stats['nohide.space']['posts'] += len(links)
                    for link in links:
                        href = link.get('href')
                        if href and "/threads/" in href:
                            href = href.strip('latest').rsplit('page-', 1)[0]
                            if href not in dupe:
                                dupe.append(href)
                                s = BeautifulSoup(requests.get("https://nohide.space"+href, headers=agent).text, 'html.parser')
                                for ele in s.find_all('div', class_='bbWrapper'):
                                    link_el = ele.find_all('a', href=True)
                                    for url in link_el:
                                        leech.handle(url['href'], "https://nohide.space"+href)
        except Exception as e: pass
        with stats_lock:
            site_stats['nohide.space']['status'] = 'Completed'


    def crackingx():
        dupe = []
        with stats_lock:
            site_stats['crackingx.com']['status'] = 'Running'
        try:
            for page in range(1, pages):
                req = requests.get(f"https://crackingx.com/forums/5/page-{page}?order=post_date&direction=desc", headers=agent)
                soup = BeautifulSoup(req.text, 'html.parser')
                target_div = soup.find('div', class_='structItemContainer-group js-threadList')
                if target_div:
                    links = target_div.find_all('a')
                    with stats_lock:
                        site_stats['crackingx.com']['posts'] += len(links)
                    for link in links:
                        href = link.get('href')
                        if href and "/threads/" in href:
                            href = href.strip('latest').rsplit('page-', 1)[0]
                            if href not in dupe:
                                dupe.append(href)
                                s = BeautifulSoup(requests.get("https://crackingx.com"+href, headers=agent).text, 'html.parser')
                                for ele in s.find_all('div', class_='bbWrapper'):
                                    link_el = ele.find_all('a', href=True)
                                    for url in link_el:
                                        leech.handle(url.get('href'), "https://crackingx.com"+href)
        except: pass
        with stats_lock:
            site_stats['crackingx.com']['status'] = 'Completed'



    def combolist():
        with stats_lock:
            site_stats['combolist.xyz']['status'] = 'Running'
        try:
            for page in range(1, pages):
                req = requests.get(f"https://www.combolist.xyz/category/combolist-5?page={page}", headers=agent)
                soup = BeautifulSoup(req.text, 'html.parser')
                read_more_elements = soup.find_all('a', class_='read-more')
                hrefs = [element['href'] for element in read_more_elements]
                with stats_lock:
                    site_stats['combolist.xyz']['posts'] += len(hrefs)
                for href in hrefs:
                    soup = BeautifulSoup(requests.get(href, headers=agent).text, 'html.parser')
                    div_element = soup.find('div', class_='article-content dont-break-out')
                    if div_element and div_element.find('a'):
                        leech.handle(div_element.find('a')['href'], href)
        except: pass
        with stats_lock:
            site_stats['combolist.xyz']['status'] = 'Completed'

def set_title(title_text):
    """Cross-platform function to set console title"""
    try:
        if os.name == 'nt':  # Windows
            os.system(f'title {title_text}')
        else:  # Unix/Linux/Mac
            print(f'\033]0;{title_text}\007', end='')
    except:
        pass  # Silently fail if title setting doesn't work

def clear_screen():
    """Clear the console screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_stats():
    """Display real-time statistics every 15 seconds"""
    global display_running, start_time
    while display_running:
        clear_screen()
        
        # Header
        print(f"{Fore.CYAN}{'='*80}")
        print(f"{Fore.CYAN}           COMBO SCRAPER by KillinMachine - Live Statistics")
        print(f"{Fore.CYAN}{'='*80}")
        
        # Runtime info
        if start_time:
            runtime = datetime.datetime.now() - start_time
            print(f"{Fore.YELLOW}Runtime: {str(runtime).split('.')[0]} | Pages per site: {pages-1} | Total Combos: {Fore.GREEN}{scraped}")
        
        print(f"{Fore.CYAN}{'-'*80}")
        
        # Site statistics table
        print(f"{Fore.WHITE}{'Site':<20} {'Status':<12} {'Posts':<8} {'Combos':<10}")
        print(f"{Fore.CYAN}{'-'*80}")
        
        with stats_lock:
            for site, stats in site_stats.items():
                status_color = Fore.GREEN if stats['status'] == 'Completed' else Fore.YELLOW if stats['status'] == 'Running' else Fore.WHITE
                print(f"{Fore.WHITE}{site:<20} {status_color}{stats['status']:<12} {Fore.BLUE}{stats['posts']:<8} {Fore.GREEN}{stats['combos']:<10}")
        
        print(f"{Fore.CYAN}{'='*80}")
        print(f"{Fore.MAGENTA}Press Ctrl+C to stop scraping")
        
        time.sleep(15)

def show_menu():
    """Display interactive menu"""
    clear_screen()
    print(f"{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}        COMBO SCRAPER by KillinMachine v2.0")
    print(f"{Fore.CYAN}{'='*70}")
    print(f"{Fore.WHITE}")
    print("Active scraping sources:")
    print(f"{Fore.GREEN}  • nohide.space         • crackingx.com")
    print(f"{Fore.GREEN}  • combolist.xyz") 
    print(f"{Fore.WHITE}")
    print("File hosting sites supported:")
    print(f"{Fore.YELLOW}  • mediafire.com        • gofile.io")
    print(f"{Fore.YELLOW}  • sendspace.com        • pixeldrain.com")
    print(f"{Fore.CYAN}{'-'*70}")
    print(f"{Fore.YELLOW}Options:")
    print(f"{Fore.WHITE}  1. Start scraping (all sites simultaneously)")
    print(f"{Fore.WHITE}  2. Exit")
    print(f"{Fore.CYAN}{'-'*70}")

def start():
    global pages, display_running, start_time
    
    while True:
        show_menu()
        choice = input(f"{Fore.LIGHTGREEN_EX}Select option (1-2): ").strip()
        
        if choice == '1':
            pages = int(input(f"{Fore.LIGHTGREEN_EX}Pages to scrape per site: ")) + 1
            
            # Initialize database
            init_database()
            
            start_time = datetime.datetime.now()
            set_title(f"Combo Scraper - Running | Pages: {pages-1}")
            
            # Start display thread
            display_thread = threading.Thread(target=display_stats, daemon=True)
            display_thread.start()
            
            # Start scraping threads
            functions = [leech.nohide, leech.crackingx, leech.combolist]
            
            threads = []
            for func in functions:
                thread = threading.Thread(target=func)
                thread.start()
                threads.append(thread)
            
            try:
                for thread in threads:
                    thread.join()
                
                display_running = False
                clear_screen()
                
                print(f"{Fore.GREEN}{'='*60}")
                print(f"{Fore.GREEN}           SCRAPING COMPLETED!")
                print(f"{Fore.GREEN}{'='*60}")
                print(f"{Fore.YELLOW}Total combos scraped: {Fore.GREEN}{scraped}")
                print(f"{Fore.YELLOW}Total runtime: {Fore.GREEN}{str(datetime.datetime.now() - start_time).split('.')[0]}")
                print(f"{Fore.YELLOW}Database: {Fore.GREEN}pulled.db")
                print(f"{Fore.GREEN}{'='*60}")
                
                input(f"{Fore.WHITE}Press Enter to return to menu...")
                display_running = True
                
            except KeyboardInterrupt:
                display_running = False
                clear_screen()
                print(f"{Fore.RED}Scraping interrupted by user!")
                input(f"{Fore.WHITE}Press Enter to return to menu...")
                display_running = True
                
        elif choice == '2':
            print(f"{Fore.GREEN}Thanks for using Combo Scraper!")
            exit()
        else:
            print(f"{Fore.RED}Invalid option! Please select 1 or 2.")
            time.sleep(2)

start()
