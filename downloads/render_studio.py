# Render Studio (turunan ReelForge V5.4)
# Ubah ZIP project Remotion dari Claude menjadi MP4 di Google Colab, tanpa instalasi di laptop.
# Jalankan SATU cell ini di Google Colab (Runtime → Ubah jenis runtime → GPU T4 bila tersedia).
import os, sys, re, json, time, shutil, zipfile, stat, secrets, threading, subprocess, urllib.request
from pathlib import Path
from collections import deque
from IPython.display import display, HTML

# Install Python server
subprocess.run([sys.executable,'-m','pip','-q','install','flask','werkzeug'],check=True)
from flask import Flask, request, jsonify, send_file, abort, Response
from werkzeug.utils import secure_filename

PORT=7860
BASE_DIR=Path('/content/render-studio').resolve()
UPLOAD_DIR=BASE_DIR/'uploads'; JOB_DIR=BASE_DIR/'jobs'
for p in (UPLOAD_DIR,JOB_DIR): p.mkdir(parents=True,exist_ok=True)
MAX_ZIP=50*1024*1024
ACCESS_PATH=secrets.token_urlsafe(18)
PREFIX='/'+ACCESS_PATH+'/'
app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=MAX_ZIP+1024*1024
lock=threading.Lock()
state={'state':'idle','stage':'Menunggu project ZIP','percent':0,'frames':'','message':'Siap','logs':deque(maxlen=100),'output':None,'requested_mode':'auto','encoder':'Belum render','render_percent':0,'fps':0,'eta_seconds':None,'elapsed_seconds':0,'total_frames':0,'current_frame':0}

def log(line):
    with lock: state['logs'].append(str(line)[-350:])
    print(str(line)[-350:],flush=True)
def update(stage=None,percent=None,status=None,message=None,frames=None):
    with lock:
        if stage is not None: state['stage']=stage
        if percent is not None: state['percent']=max(state['percent'],int(percent))
        if status is not None: state['state']=status
        if message is not None: state['message']=message
        if frames is not None: state['frames']=frames

def cmd(args,cwd=None,base=None,range_span=None,env=None):
    # Output render diproses per baris. Log Chrome hanya disimpan bila berupa error;
    # info delayRender() di setiap frame dibuang.
    log('[COMMAND] '+' '.join(map(str,args)))
    proc=subprocess.Popen(args,cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,
        text=True,encoding='utf8',errors='replace',bufsize=1,
        env={**os.environ,'FORCE_COLOR':'0','CI':'1',**(env or {})})
    strip_ansi=lambda s: re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',s).strip()
    frame_re=re.compile(r'\bRendered\s+(?:frame\s+)?(\d+)\s*/\s*(\d+)\b',re.I)
    recent=deque(maxlen=30)
    frame_samples=deque(maxlen=50)
    started=time.monotonic()
    last_report=0.0
    last_reported_pct=-1
    last_stage=''
    try:
        for raw in proc.stdout:
            line=strip_ansi(raw)
            if not line: continue
            recent.append(line)
            lower=line.lower()

            # Info internal Chromium yang tidak berguna untuk pengguna.
            if ('delayrender()' in lower or 'setting the current frame' in lower) and not re.search(r'error|failed|timeout',lower):
                continue
            if re.search(r'\bchrome\s+\[.*\binfo:console:',line,re.I):
                continue
            if re.search(r'^Tab\s+\d+\s+',line,re.I) and not re.search(r'error|failed|timeout',lower):
                continue

            match=frame_re.search(line)
            if match and base is not None:
                done,total=map(int,match.groups())
                if total<=0: continue
                done=max(0,min(done,total))
                now=time.monotonic()
                frame_samples.append((now,done))
                while len(frame_samples)>2 and now-frame_samples[0][0]>14:
                    frame_samples.popleft()
                dt=frame_samples[-1][0]-frame_samples[0][0]
                df=frame_samples[-1][1]-frame_samples[0][1]
                speed=round(df/dt,2) if dt>0.1 and df>=0 else 0.0
                eta=round((total-done)/speed) if speed>0 else None
                render_pct=round(100*done/total,1)
                overall=min(98,int(base+(range_span or 0)*done/total))
                elapsed=int(now-started)
                with lock:
                    state.update(percent=max(state['percent'],overall),frames=f'{done}/{total}',
                        render_percent=render_pct,fps=speed,eta_seconds=eta,
                        elapsed_seconds=elapsed,total_frames=total,current_frame=done,
                        message=f'{render_pct:.1f}% • {done}/{total} frame')
                # Hindari banjir log: maksimal satu baris tiap ±2 detik, kecuali kelipatan 5% dan frame terakhir.
                milestone=int(render_pct//5)
                report=(now-last_report>=2.0 or (milestone!=last_reported_pct and now-last_report>=0.5) or done==total)
                if report:
                    eta_label=(f'{eta//60}m {eta%60:02d}s' if eta is not None else 'menghitung...')
                    log(f'[RENDER] {render_pct:.1f}% | Frame {done:,}/{total:,} | {speed:.1f} frame/detik | Sisa ~{eta_label}')
                    last_report=now
                    last_reported_pct=milestone
                continue

            if re.search(r'(encoding|encoded|muxing|writing.*mp4|video.*saved)',lower):
                phase='encoding'
                if phase!=last_stage:
                    log('[ENCODE] '+line[:260]);last_stage=phase
                continue
            if re.search(r'(bundling|bundle complete|bundle size)',lower):
                phase='bundling'
                if phase!=last_stage:
                    log('[BUNDLE] '+line[:260]);last_stage=phase
                continue
            if re.search(r'\b(error|failed|failure|warning|warn|timeout|cannot|exception|out of memory)\b',lower):
                log('[WARN/ERROR] '+line[:500])
                continue
            # Baris verbose biasa sengaja disembunyikan.
    finally:
        if proc.stdout: proc.stdout.close()
    rc=proc.wait()
    if rc:
        raise RuntimeError(f'Command gagal ({rc}): '+' | '.join(recent)[-2000:])
    if base is not None:
        log('[RENDER] Proses frame selesai; memvalidasi output MP4...')

def safe_extract(zpath,target):
    with zipfile.ZipFile(zpath) as z:
        entries=z.infolist()
        if len(entries)>3000: raise ValueError('ZIP memiliki terlalu banyak file (>3000).')
        if sum(x.file_size for x in entries)>450*1024*1024: raise ValueError('ZIP terlalu besar setelah ekstraksi.')
        for m in entries:
            name=m.filename
            dest=(target/name).resolve()
            if not dest.is_relative_to(target.resolve()): raise ValueError('ZIP memiliki path tidak aman.')
            mode=(m.external_attr>>16)&0o170000
            if mode==stat.S_IFLNK: raise ValueError('ZIP symbolic link tidak diizinkan.')
            if m.is_dir():dest.mkdir(parents=True,exist_ok=True)
            else:
                dest.parent.mkdir(parents=True,exist_ok=True)
                with z.open(m) as src,open(dest,'wb') as dst: shutil.copyfileobj(src,dst)

# Setiap ZIP memakai dependency-nya sendiri. Cache npm bersama mempercepat instalasi berikutnya
# tanpa memaksa versi tertentu.
RUNTIME_DIR = BASE_DIR / 'runtime_deps'
NPM_CACHE = BASE_DIR / 'npm-cache'
setup_status = {'ready': False, 'message': 'Menyiapkan environment', 'nvenc': False,
                'gpu': 'Tidak terdeteksi', 'node': '-', 'npm': '-',
                'install_policy': 'per-project', 'remotion_version': 'mengikuti project'}

def install_project_deps(project):
    manifest_path = project/'package.json'
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except Exception as e:
        raise ValueError('package.json tidak valid: '+str(e))
    if not isinstance(manifest,dict):
        raise ValueError('package.json harus berupa JSON object.')
    req = {**manifest.get('dependencies',{}), **manifest.get('devDependencies',{})}
    if not ('remotion' in req and '@remotion/cli' in req):
        raise ValueError('Project harus berisi remotion dan @remotion/cli di dependencies/devDependencies.')
    # Tolak path lokal, URL git, dan npm workspace dari ZIP.
    for name, version in req.items():
        if not isinstance(version,str) or version.startswith(('file:', 'link:', 'git+', 'git:', 'http:', 'https:', 'workspace:')):
            raise ValueError(f'Dependency tidak didukung: {name}@{version}')
    log('[DEPENDENCY] '+', '.join(f'{k}@{v}' for k,v in req.items())[:900])
    update('Instal dependency sesuai project',28,'installing','npm sedang menyiapkan dependency ZIP ini')
    env={**os.environ,'npm_config_cache':str(NPM_CACHE),'npm_config_fund':'false','npm_config_audit':'false'}
    NPM_CACHE.mkdir(parents=True,exist_ok=True)
    # Hapus node_modules bawaan ZIP agar ZIP tidak mengendalikan isi binary yang terpasang.
    nm=project/'node_modules'
    if nm.is_symlink():nm.unlink()
    elif nm.exists():shutil.rmtree(nm)
    lock_file=project/'package-lock.json'
    if lock_file.exists():
        log('[INSTALL] npm ci berdasarkan package-lock.json')
        command=['npm','ci','--no-audit','--no-fund','--prefer-offline','--no-progress']
    else:
        log('[INSTALL] package-lock.json tidak ada (umum untuk ZIP dari Claude), memakai npm install')
        command=['npm','install','--no-audit','--no-fund','--prefer-offline','--no-progress']
    try:
        cmd(command,cwd=project,env=env)
    except RuntimeError:
        if not lock_file.exists():
            raise
        log('[INSTALL WARN] npm ci gagal; mencoba npm install untuk memperbaiki lockfile.')
        cmd(['npm','install','--no-audit','--no-fund','--prefer-offline','--no-progress'],cwd=project,env=env)
    executable=project/'node_modules'/'.bin'/'remotion'
    if not executable.exists():raise RuntimeError('Remotion CLI tidak ditemukan setelah npm install.')
    log('[INSTALL OK] Dependency project siap.')
    return executable

def render_job(archive, mode='auto'):
    try:
        if not setup_status['ready']:
            raise RuntimeError('Environment belum siap. Jalankan ulang cell Colab.')
        working=JOB_DIR/'current'
        if working.exists():shutil.rmtree(working)
        working.mkdir(parents=True)
        update('Ekstrak ZIP',12,'extracting')
        safe_extract(archive,working)
        log('[OK] ZIP berhasil diekstrak')
        matches=[p.parent for p in working.rglob('package.json') if (p.parent/'src/index.ts').is_file() and 'node_modules' not in p.parts]
        if not matches: raise RuntimeError('Tidak ditemukan src/index.ts dan package.json dalam ZIP.')
        project=matches[0]
        log(f'[PROJECT] {project.name}')
        update('Baca package.json',23,'validating')
        remotion_bin=install_project_deps(project)
        update('Periksa komposisi video',49,'compositions')
        # Pakai Chrome yang diunduh saat setup, bukan unduh ulang per ZIP.
        browsers=list((RUNTIME_DIR/'node_modules'/'.remotion').glob('chrome-headless-shell/**/chrome-headless-shell'))
        browser_flag=['--browser-executable='+str(browsers[0])] if browsers else []
        # Baca ID komposisi dari project. MainReel diutamakan, lalu komposisi pertama yang ditemukan.
        discovery=subprocess.run(
            [str(remotion_bin),'compositions','src/index.ts','--quiet']+browser_flag,
            cwd=str(project),capture_output=True,text=True,timeout=180,
            env={**os.environ,'FORCE_COLOR':'0','CI':'1'}
        )
        if discovery.returncode != 0:
            raise RuntimeError('Gagal membaca composition: '+(discovery.stderr or discovery.stdout)[-1300:])
        lines=[s.strip() for s in discovery.stdout.splitlines() if s.strip()]
        if len(lines)==1:
            ids=lines[0].split()
        else:
            ids=[s for s in lines if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',s)]
        if not ids:
            raise RuntimeError('Tidak ada composition ID terbaca. Output: '+discovery.stdout[-900:])
        composition_id='MainReel' if 'MainReel' in ids else ids[0]
        log('[COMPOSITION] Terdeteksi: '+', '.join(ids[:12]))
        log('[COMPOSITION] Dipilih otomatis: '+composition_id)
        output=BASE_DIR/'reel_final.mp4'
        if output.exists():output.unlink()
        render_base=[str(remotion_bin),'render','src/index.ts',composition_id,str(output),'--codec=h264','--audio-codec=aac','--pixel-format=yuv420p','--concurrency=1','--timeout=120000','--log=verbose','--overwrite']+browser_flag
        gpu_wanted=(mode in ('auto','gpu') and setup_status['nvenc'])
        if mode=='gpu' and not setup_status['nvenc']:
            log('[WARN] NVENC tidak tersedia; memakai CPU.')
        if gpu_wanted:
            log('[GPU] Mencoba Remotion hardware acceleration NVENC.')
            with lock:state['encoder']='GPU NVENC (percobaan)'
            update('Render dengan GPU NVENC',60,'rendering','Memproses video')
            try:
                cmd(render_base+['--hardware-acceleration=required','--video-bitrate=8M'],cwd=project,base=60,range_span=38)
                with lock:state['encoder']='GPU NVENC'
            except Exception as gpu_error:
                log('[GPU WARN] '+str(gpu_error)[-650:])
                log('[FALLBACK] GPU gagal; mencoba CPU H.264.')
                with lock: state.update(percent=60,render_percent=0,fps=0,eta_seconds=None,elapsed_seconds=0,total_frames=0,current_frame=0,frames='')
                if output.exists():output.unlink()
                with lock:state['encoder']='CPU H.264 (fallback)'
                update('Fallback GPU → CPU',60,'rendering')
                cmd(render_base+['--hardware-acceleration=disable'],cwd=project,base=60,range_span=38)
        else:
            with lock:state['encoder']='CPU H.264'
            update('Render dengan CPU H.264',60,'rendering')
            cmd(render_base+['--hardware-acceleration=disable'],cwd=project,base=60,range_span=38)
        if not output.exists() or output.stat().st_size<1000:raise RuntimeError('Video output tidak ditemukan.')
        with lock:state['output']=str(output)
        update('Video selesai, siap diputar',100,'done',f'Ukuran MP4 {output.stat().st_size/1048576:.2f} MB')
        log('[SUCCESS] Video selesai. Encoder: '+state['encoder']+' | Ukuran: '+f'{output.stat().st_size/1048576:.2f} MB')
    except Exception as e:
        log('[ERROR] '+str(e));update('Render gagal',None,'error',str(e))

# SETUP SEKALI: dijalankan sebelum web dibuka.
print('\n[SETUP] Menyiapkan seluruh kebutuhan sebelum web dibuka...',flush=True)
subprocess.run(['apt-get','update','-qq'],check=True)
linux_packages=['ffmpeg','libnss3','libnspr4','libdbus-1-3','libatk1.0-0','libatk-bridge2.0-0','libcups2','libdrm2','libxkbcommon0','libxcomposite1','libxdamage1','libxfixes3','libxrandr2','libgbm1','fonts-liberation']
for pkg in linux_packages:
    rc=subprocess.run(['apt-get','install','-y','-qq',pkg],capture_output=True,text=True)
    if rc.returncode: print('[SETUP WARN]',pkg,rc.stderr[-200:])
for audio_pkg in ('libasound2t64','libasound2'):
    policy=subprocess.run(['apt-cache','policy',audio_pkg],capture_output=True,text=True)
    if 'Candidate:' in policy.stdout and 'Candidate: (none)' not in policy.stdout:
        subprocess.run(['apt-get','install','-y','-qq',audio_pkg],check=True)
        break
if not shutil.which('node') or not shutil.which('npm'):
    raise RuntimeError('Node.js/npm tidak tersedia di Colab.')
if not shutil.which('ffmpeg'):
    raise RuntimeError('ffmpeg belum tersedia. Periksa instalasi Colab.')
setup_status['node']=subprocess.check_output(['node','--version'],text=True).strip()
setup_status['npm']=subprocess.check_output(['npm','--version'],text=True).strip()
print('[SETUP] Node',setup_status['node'])
print('[SETUP] npm',setup_status['npm'])

RUNTIME_DIR.mkdir(parents=True,exist_ok=True)
bootstrap_manifest={'name':'render-studio-browser-bootstrap','private':True,'version':'1.0.0',
                    'dependencies':{'@remotion/cli':'4.0.484','remotion':'4.0.484'}}
(RUNTIME_DIR/'package.json').write_text(json.dumps(bootstrap_manifest,indent=2),encoding='utf8')
bootstrap_remotion=RUNTIME_DIR/'node_modules'/'.bin'/'remotion'
if not bootstrap_remotion.exists():
    print('[SETUP] Menyiapkan browser Remotion untuk semua project...')
    cmd(['npm','install','--no-audit','--no-fund'],cwd=RUNTIME_DIR)
print('[SETUP] Validasi Chromium Remotion...')
chrome_candidates=list((RUNTIME_DIR/'node_modules'/'.remotion').glob('chrome-headless-shell/**/chrome-headless-shell'))
if chrome_candidates and chrome_candidates[0].is_file():
    print('[BROWSER OK] Chrome Headless Shell sudah tersedia:', chrome_candidates[0])
else:
    print('[SETUP] Browser belum ada; download satu kali...')
    cmd([str(bootstrap_remotion),'browser','ensure'],cwd=RUNTIME_DIR)
    chrome_candidates=list((RUNTIME_DIR/'node_modules'/'.remotion').glob('chrome-headless-shell/**/chrome-headless-shell'))
    if not chrome_candidates:
        raise RuntimeError('Chromium belum ditemukan setelah browser ensure.')
    print('[BROWSER OK] Chromium sudah terinstal.')

# Deteksi GPU NVIDIA dan uji encoding NVENC sungguhan sebelum web dibuka.
print('[SETUP] Deteksi GPU NVIDIA dan uji encoding NVENC...')
try:
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], capture_output=True, text=True, timeout=12)
    setup_status['gpu'] = gpu.stdout.strip().splitlines()[0] if gpu.returncode == 0 and gpu.stdout.strip() else 'Tidak terdeteksi'
except Exception as e:
    print('[GPU INFO]', str(e))
try:
    nvtest=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=black:s=1280x720:r=30','-frames:v','3','-c:v','h264_nvenc','-f','null','-'],capture_output=True,text=True,timeout=30)
    setup_status['nvenc']=(nvtest.returncode==0)
    if not setup_status['nvenc']: print('[GPU WARN] NVENC test gagal:',nvtest.stderr[-500:])
except Exception as e:
    print('[GPU WARN] NVENC test gagal:',e)
print('[SETUP] GPU:', setup_status['gpu'], '| NVENC:',setup_status['nvenc'])
if not shutil.which('cloudflared'):
    url='https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64'
    print('[SETUP] Download Cloudflare Quick Tunnel...')
    urllib.request.urlretrieve(url,'/usr/local/bin/cloudflared')
    os.chmod('/usr/local/bin/cloudflared',0o755)
setup_status.update(ready=True,message='Node, npm, Chromium, FFmpeg, dan tunnel siap; dependency mengikuti tiap ZIP')
print('[SETUP] ✅ SEMUA BERHASIL. Dependency setiap ZIP diinstal setelah ekstraksi, sebelum render.',flush=True)

# Tampilan krem, navy, teal, dan judul serif. Tanpa CSS/font eksternal.
HTML_TEMPLATE=r'''<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Render Studio</title>
<style>
:root{--navy-900:#0f1b33;--navy-800:#16264a;--navy-600:#33456b;--ink:#1b2436;--muted:#4d5770;--paper:#faf7f2;--paper-2:#f2ede4;--line:#e2dbcf;--teal-700:#0b6b63;--teal-600:#0f7a71;--teal-100:#d9efec;--teal-300:#8fd8cf;--amber-100:#fbefd5;--amber-800:#7a4b00;--radius:14px;--font:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans",Ubuntu,sans-serif;--serif:Georgia,"Iowan Old Style","Times New Roman",serif}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:5rem}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
body{margin:0;font-family:var(--font);font-size:1.0625rem;line-height:1.65;color:var(--ink);background:var(--paper)}
a{color:var(--teal-700);text-underline-offset:3px}a:hover{color:var(--navy-800)}
:focus-visible{outline:3px solid var(--teal-600);outline-offset:3px;border-radius:4px}
.panel-dark :focus-visible,.site-footer :focus-visible{outline-color:var(--teal-100)}
h1,h2,h3{font-family:var(--serif);color:var(--navy-900);line-height:1.2;margin:0 0 .6rem}
h1{font-size:clamp(2rem,5vw,3.2rem);letter-spacing:-.01em}h2{font-size:clamp(1.4rem,3vw,1.9rem)}h3{font-size:1.15rem}
.container{width:min(100% - 2.5rem,72rem);margin-inline:auto}
.site-header{position:sticky;top:0;z-index:20;background:rgba(250,247,242,.94);backdrop-filter:saturate(150%) blur(8px);border-bottom:1px solid var(--line)}
.nav{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:.25rem 1rem;min-height:4rem}
.brand{display:inline-flex;align-items:center;gap:.6rem;font-weight:700;color:var(--navy-900);text-decoration:none}
.brand-mark{width:2rem;height:2rem;border-radius:9px;display:grid;place-items:center;background:var(--navy-900);color:var(--paper);font-family:var(--serif);box-shadow:inset 0 -4px 0 var(--teal-600)}
.brand small{font-weight:600;color:var(--teal-700);background:var(--teal-100);border-radius:999px;padding:.1rem .55rem;font-size:.75rem}
.nav-links{display:flex;flex-wrap:wrap;gap:.25rem;list-style:none;margin:0;padding:0}
.nav-links a{display:flex;align-items:center;min-height:44px;padding:.5rem .8rem;border-radius:8px;color:var(--navy-800);text-decoration:none;font-weight:500;font-size:.98rem}
.nav-links a:hover{background:var(--paper-2)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.5rem;padding:.8rem 1.25rem;border-radius:10px;font:inherit;font-weight:600;text-decoration:none;border:2px solid transparent;line-height:1.2;min-height:44px;cursor:pointer}
.btn-primary{background:var(--teal-700);color:#fff}.btn-primary:hover{background:var(--navy-800);color:#fff}
.btn-secondary{background:transparent;color:var(--navy-800);border-color:var(--navy-600)}.btn-secondary:hover{background:var(--navy-900);color:#fff;border-color:var(--navy-900)}
.btn-light{background:var(--teal-300);color:var(--navy-900)}.btn-light:hover{background:#fff;color:var(--navy-900)}
.btn[disabled]{opacity:.6;cursor:progress}
.btn-row{display:flex;flex-wrap:wrap;gap:.75rem;margin-top:1.5rem}
.eyebrow{display:block;font-size:.8rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--teal-700);margin:0 0 .75rem}
.lead{font-size:1.15rem;color:var(--muted);max-width:36rem}
.hero{padding:clamp(2.5rem,7vw,5rem) 0 clamp(2rem,5vw,3.5rem)}
.hero-grid{display:grid;grid-template-columns:1.3fr 1fr;gap:clamp(1.5rem,5vw,3.5rem);align-items:center}
.panel-dark{position:relative;overflow:hidden;background:var(--navy-900);color:#e9edf5;border-radius:20px;padding:1.6rem}
.panel-dark::after{content:"";position:absolute;right:-3rem;bottom:-3rem;width:10rem;height:10rem;border-radius:50%;border:22px solid rgba(15,122,113,.45);pointer-events:none}
.panel-dark > *{position:relative;z-index:1}
.panel-dark h2,.panel-dark h3{color:#fff}
.status-list{list-style:none;margin:0;padding:0;display:grid;gap:.55rem;position:relative;z-index:1}
.status-list li{display:flex;justify-content:space-between;gap:1rem;border-bottom:1px solid rgba(255,255,255,.1);padding-bottom:.45rem}
.status-list span{color:#aab8d2}.status-list b{color:#fff;text-align:right}
.badge{display:inline-block;font-size:.78rem;font-weight:700;padding:.2rem .6rem;border-radius:999px;background:var(--teal-100);color:var(--teal-700)}
.badge.cpu{background:var(--amber-100);color:var(--amber-800)}
.section{padding:clamp(2.5rem,6vw,4rem) 0;border-top:1px solid var(--line)}
.section-alt{background:var(--paper-2)}
.section-head{max-width:40rem;margin-bottom:1.75rem}.section-head p{color:var(--muted);margin:0}
.flow{list-style:none;margin:0;padding:0;display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(min(14rem,100%),1fr));counter-reset:f}
.flow li{counter-increment:f;background:#fff;border:1px solid var(--line);border-top:4px solid var(--teal-600);border-radius:var(--radius);padding:1.2rem}
.flow li::before{content:counter(f);display:inline-grid;place-items:center;width:2rem;height:2rem;border-radius:50%;background:var(--teal-700);color:#fff;font-weight:700;margin-bottom:.5rem}
.flow p{margin:0;color:var(--muted)}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.05fr);gap:clamp(1.25rem,3vw,2rem);align-items:start}
.card{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:clamp(1.2rem,3vw,1.6rem)}
.drop{display:block;border:2px dashed var(--navy-600);border-radius:var(--radius);padding:1.8rem 1rem;text-align:center;background:var(--paper);cursor:pointer;transition:background .2s,border-color .2s}
.drop:hover,.drop.drag{border-color:var(--teal-600);background:var(--teal-100)}
.drop strong{display:block;color:var(--navy-900);font-size:1.05rem}.drop span{color:var(--muted);font-size:.93rem}
.drop input{position:absolute;width:1px;height:1px;opacity:0}
.fname{margin:.75rem 0 0;font-weight:600;color:var(--teal-700);word-break:break-all}
fieldset{border:0;margin:1.25rem 0 0;padding:0}legend{font-weight:700;color:var(--navy-900);margin-bottom:.5rem}
.modes{display:grid;gap:.5rem;grid-template-columns:repeat(3,minmax(0,1fr))}
.modes label{display:flex;gap:.5rem;align-items:flex-start;border:1px solid var(--line);border-radius:10px;padding:.75rem;cursor:pointer;background:var(--paper);font-weight:600;color:var(--navy-900)}
.modes label:has(input:checked){border-color:var(--teal-600);background:var(--teal-100);box-shadow:inset 0 0 0 1px var(--teal-600)}
.modes input{accent-color:var(--teal-700);margin-top:.3rem}
.modes small{display:block;font-weight:400;color:var(--muted);font-size:.85rem;line-height:1.4}
.hint{margin:.6rem 0 0;color:var(--muted);font-size:.93rem}
.trust{display:flex;gap:.6rem;align-items:flex-start;margin:1.25rem 0;font-size:.95rem;color:var(--ink)}
.trust input{width:1.2rem;height:1.2rem;margin-top:.2rem;accent-color:var(--teal-700)}
.wide{width:100%}
.callout{border-left:4px solid #b26b00;background:var(--amber-100);padding:.9rem 1.1rem;border-radius:0 10px 10px 0;margin:1.25rem 0 0;font-size:.95rem}
.callout p{margin:0}
.progress-head{display:flex;justify-content:space-between;gap:1rem;align-items:baseline}
.progress-head b{color:#fff}.progress-head .pct{font-size:1.6rem;font-family:var(--serif);color:var(--teal-300)}
.bar{height:12px;border-radius:12px;background:rgba(255,255,255,.12);overflow:hidden;margin:.75rem 0}
.fill{height:100%;width:0;background:linear-gradient(90deg,var(--teal-600),var(--teal-300));transition:width .35s}
.meta-dark{margin:0;color:#c9d1e2;font-size:.93rem}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.5rem;margin:1rem 0}
.metrics div{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:.55rem .7rem}
.metrics span{display:block;font-size:.75rem;letter-spacing:.06em;text-transform:uppercase;color:#aab8d2}
.metrics b{color:#fff;font-variant-numeric:tabular-nums}
.console{height:12rem;overflow:auto;margin:0;padding:.9rem 1rem;border-radius:12px;background:#0a1428;border:1px solid rgba(255,255,255,.12);color:#cfe6dc;font:.8rem/1.65 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
.player{margin-top:1rem;padding:1rem;border-radius:var(--radius);background:#fff;color:var(--ink)}
.player h3{color:var(--navy-900)}
.player video{display:block;width:100%;max-width:18rem;max-height:30rem;margin:0 auto 1rem;border-radius:12px;background:#000}
.tools{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(min(16rem,100%),1fr))}
.tools .card p{color:var(--muted)}
.site-footer{background:var(--navy-900);color:#c9d1e2;padding:2rem 0;font-size:.95rem}
.site-footer a{color:#fff}
.toast{position:fixed;left:50%;bottom:1.25rem;transform:translateX(-50%);z-index:30;max-width:calc(100% - 2rem);background:var(--navy-900);color:#fff;border-radius:12px;padding:.8rem 1.1rem;box-shadow:0 14px 30px -12px rgba(15,27,51,.6);display:none}
@media (max-width:860px){.hero-grid,.grid{grid-template-columns:1fr}}
@media (max-width:560px){.modes,.metrics{grid-template-columns:1fr 1fr}.nav-links{display:none}}
</style>
</head>
<body>
<header class="site-header"><nav class="container nav" aria-label="Navigasi">
  <a class="brand" href="#atas"><span class="brand-mark" aria-hidden="true">R</span>Render Studio</a>
  <ul class="nav-links">
    <li><a href="#cara">Cara pakai</a></li>
    <li><a href="#render">Render</a></li>
    <li><a href="#persiapan">Persiapan</a></li>
  </ul>
</nav></header>
<main id="atas">
  <section class="hero"><div class="container hero-grid">
    <div>
      <span class="eyebrow">Render Studio · Google Colab</span>
      <h1>Ubah ZIP Remotion jadi MP4, tanpa instalasi di laptop.</h1>
      <p class="lead">Upload ZIP project dari Claude. Studio ini memasang dependency sesuai project, merender video 1080×1920, lalu menampilkan MP4 yang siap diunduh.</p>
      <div class="btn-row">
        <a class="btn btn-primary" href="#render">Mulai render</a>
        <a class="btn btn-secondary" href="#persiapan">Persiapan project</a>
      </div>
    </div>
    <aside class="panel-dark" aria-labelledby="server-heading">
      <h2 id="server-heading">Status server</h2>
      <ul class="status-list">
        <li><span>Akselerasi</span><b><span id="gpuBadge" class="badge">Memeriksa…</span></b></li>
        <li><span>GPU</span><b id="gpuName">-</b></li>
        <li><span>Node.js / npm</span><b id="nodeInfo">-</b></li>
        <li><span>Dependency</span><b>mengikuti tiap ZIP</b></li>
      </ul>
    </aside>
  </div></section>

  <section class="section section-alt" id="cara"><div class="container">
    <div class="section-head"><h2>Cara pakai</h2><p>Biarkan tab Colab tetap terbuka selama memakai studio ini.</p></div>
    <ol class="flow">
      <li><h3>Siapkan ZIP</h3><p>Unduh <code>remotion_reels_[topik].zip</code> dari Claude, berisi source, audio Cartesia, dan aset lokal.</p></li>
      <li><h3>Upload dan render</h3><p>Pilih mode render, centang konfirmasi, lalu klik Upload &amp; Render. Progres tampil langsung.</p></li>
      <li><h3>Unduh MP4</h3><p>Putar hasilnya di panel kanan, lalu unduh dan unggah ke Instagram Reels.</p></li>
    </ol>
  </div></section>

  <section class="section" id="render"><div class="container">
    <div class="section-head"><span class="eyebrow">Render</span><h2>ZIP → Video MP4</h2><p>Maksimal 50 MB. Setiap ZIP diekstrak, diinstal dependency-nya (npm ci atau npm install), lalu dirender.</p></div>
    <div class="grid">
      <div class="card">
        <label class="drop" id="drop" for="zipFile">
          <strong>Pilih atau seret file ZIP</strong>
          <span>Project Remotion lengkap dengan package.json dan src/index.ts</span>
          <input id="zipFile" type="file" accept=".zip,application/zip">
        </label>
        <p id="fileName" class="fname" role="status">Belum ada file dipilih</p>
        <fieldset>
          <legend>Mode render</legend>
          <div class="modes">
            <label><input type="radio" name="renderMode" value="auto" checked><span>Auto<small>GPU bila tersedia, CPU sebagai cadangan</small></span></label>
            <label><input type="radio" name="renderMode" value="gpu"><span>GPU NVENC<small>Encode H.264 di NVIDIA</small></span></label>
            <label><input type="radio" name="renderMode" value="cpu"><span>CPU H.264<small>Kompatibilitas maksimal</small></span></label>
          </div>
          <p id="gpuHint" class="hint">Memeriksa status perangkat…</p>
        </fieldset>
        <label class="trust"><input type="checkbox" id="trustedProject"> <span>Saya hanya mengunggah ZIP yang saya buat sendiri atau percayai. <code>npm install</code> dapat menjalankan kode dari project.</span></label>
        <button id="renderBtn" class="btn btn-primary wide" type="button">Upload &amp; Render MP4</button>
        <div class="callout"><p><strong>Perhatian:</strong> siapa pun yang memiliki URL studio ini bisa mengaksesnya. Jangan bagikan link-nya secara publik.</p></div>
      </div>

      <section class="panel-dark" aria-labelledby="progress-heading">
        <h2 id="progress-heading" class="sr-only" style="position:absolute;left:-9999px">Progres render</h2>
        <div class="progress-head"><b id="stage">Menunggu project</b><span class="pct" id="percentage">0%</span></div>
        <div class="bar" role="progressbar" aria-labelledby="stage" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" id="progressBar"><div class="fill" id="progressFill"></div></div>
        <p class="meta-dark" id="frames">Progres diperbarui selama proses berlangsung.</p>
        <div class="metrics">
          <div><span>Render</span><b id="mRender">0%</b></div>
          <div><span>Kecepatan</span><b id="mFps">0 fps</b></div>
          <div><span>Sisa</span><b id="mEta">—</b></div>
          <div><span>Berjalan</span><b id="mElapsed">0m 00s</b></div>
        </div>
        <p class="meta-dark" id="encoderInfo">Encoder: belum render</p>
        <pre class="console" id="logs" aria-live="polite">[READY] Studio siap menerima project ZIP.</pre>
        <div class="player" id="player" hidden>
          <h3>✓ Video siap diputar</h3>
          <video id="preview" controls playsinline preload="metadata"></video>
          <a id="downloadBtn" class="btn btn-primary wide" download="reels_video.mp4">Unduh MP4</a>
        </div>
      </section>
    </div>
  </div></section>

  <section class="section section-alt" id="persiapan"><div class="container">
    <div class="section-head"><span class="eyebrow">Belum punya ZIP?</span><h2>Siapkan project Remotion</h2><p>Siapkan storyboard dan audio sebelum membuat project video.</p></div>
    <div class="tools">
      <div class="card"><h3>1 · Storyboard dan voice-over</h3><p>Siapkan storyboard TXT, teks voice-over final, dan audio narasi sesuai durasi video.</p></div>
      <div class="card"><h3>2 · Project Remotion</h3><p>Kemas source, audio, aset lokal, package.json, dan src/index.ts dalam ZIP, lalu unggah ke panel render.</p></div>
    </div>
  </div></section>
</main>
<footer class="site-footer"><div class="container"><p><strong>Render Studio</strong> · Berjalan sementara di Google Colab.</p></div></footer>
<div class="toast" id="toast" role="status"></div>
<script>
const BASE=__BASE_JSON__;
let polling=null, selectedFile=null;
const $=id=>document.getElementById(id);
function toast(t){$('toast').textContent=t;$('toast').style.display='block';clearTimeout(toast.t);toast.t=setTimeout(()=>$('toast').style.display='none',2800)}
function fmtTime(v){return v==null?'menghitung…':Math.floor(v/60)+'m '+String(Math.floor(v%60)).padStart(2,'0')+'s'}
function showFile(f){if(!f)return;if(!f.name.toLowerCase().endsWith('.zip')){toast('Pilih file ZIP');return}selectedFile=f;$('fileName').textContent='✓ '+f.name+' ('+(f.size/1024/1024).toFixed(2)+' MB)'}
$('zipFile').addEventListener('change',e=>showFile(e.target.files[0]));
for(const e of ['dragenter','dragover'])$('drop').addEventListener(e,x=>{x.preventDefault();$('drop').classList.add('drag')});
for(const e of ['dragleave','drop'])$('drop').addEventListener(e,x=>{x.preventDefault();$('drop').classList.remove('drag')});
$('drop').addEventListener('drop',e=>showFile(e.dataTransfer.files[0]));
function updateStatus(s){
  const pct=Math.max(0,Math.min(100,s.percent||0));
  $('percentage').textContent=pct+'%';$('progressFill').style.width=pct+'%';$('progressBar').setAttribute('aria-valuenow',pct);
  $('stage').textContent=s.stage||'Menunggu';
  $('frames').textContent=s.frames?s.frames+' frame diproses':(s.message||'');
  $('logs').textContent=(s.logs||[]).join('\n')||'[READY]';$('logs').scrollTop=$('logs').scrollHeight;
  $('encoderInfo').textContent='Encoder: '+(s.encoder||'belum render');
  $('mRender').textContent=(s.render_percent||0)+'%';$('mFps').textContent=(s.fps||0)+' fps';
  $('mEta').textContent=s.state==='rendering'?fmtTime(s.eta_seconds):'—';$('mElapsed').textContent=fmtTime(s.elapsed_seconds||0);
  const busy=['uploading','extracting','validating','installing','compositions','rendering'].includes(s.state);
  $('renderBtn').disabled=busy;$('renderBtn').textContent=busy?'Proses sedang berjalan…':'Upload & Render MP4';
  if(s.state==='done'){$('player').hidden=false;if(!$('preview').getAttribute('src')){$('preview').src=BASE+'video?ts='+Date.now();$('downloadBtn').href=BASE+'download'}clearInterval(polling);polling=null}
  if(s.state==='error'){toast('Render gagal. Lihat log untuk detail.');clearInterval(polling);polling=null}
}
async function check(){try{const r=await fetch(BASE+'status',{cache:'no-store'});if(r.ok)updateStatus(await r.json())}catch(e){console.log(e)}}
async function startRender(){
  if(!$('trustedProject').checked){toast('Centang konfirmasi ZIP tepercaya dulu');return}
  if(!selectedFile){toast('Pilih ZIP terlebih dahulu');return}
  if(selectedFile.size>50*1024*1024){toast('ZIP maksimal 50 MB');return}
  $('player').hidden=true;$('preview').removeAttribute('src');$('preview').load();
  $('renderBtn').disabled=true;$('stage').textContent='Mengupload ZIP…';$('logs').textContent='[UPLOAD] Mengirim ZIP ke Colab…';
  const fd=new FormData();fd.append('project',selectedFile);fd.append('trusted','yes');fd.append('mode',document.querySelector('input[name=renderMode]:checked').value);
  try{const r=await fetch(BASE+'upload',{method:'POST',body:fd});const data=await r.json();if(!r.ok)throw Error(data.error||'Upload gagal');await check();if(polling)clearInterval(polling);polling=setInterval(check,1200)}
  catch(e){toast(e.message);$('renderBtn').disabled=false;$('stage').textContent='Upload ditolak';$('logs').textContent='[ERROR] '+e.message;await check()}
}
$('renderBtn').addEventListener('click',startRender);
async function refreshEnv(){try{const r=await fetch(BASE+'environment',{cache:'no-store'});const e=await r.json();
  $('gpuBadge').textContent=e.nvenc?'GPU NVENC siap':'CPU siap';$('gpuBadge').classList.toggle('cpu',!e.nvenc);
  $('gpuName').textContent=e.gpu||'Tidak terdeteksi';$('nodeInfo').textContent=(e.node||'-')+' / '+(e.npm||'-');
  $('gpuHint').textContent='GPU: '+(e.gpu||'Tidak terdeteksi')+' · NVENC: '+(e.nvenc?'berhasil diuji':'tidak tersedia, render memakai CPU');
}catch(err){$('gpuHint').textContent='Gagal membaca status perangkat'}}
refreshEnv();check();
</script>
</body>
</html>'''
PAGE=HTML_TEMPLATE.replace('__BASE_JSON__',json.dumps(PREFIX))

@app.route(PREFIX)
def home():return Response(PAGE,mimetype='text/html')

@app.route(PREFIX+'status')
def status():
    with lock:
        return jsonify({k:(list(v) if k=='logs' else v) for k,v in state.items() if k!='output'})

@app.route(PREFIX+'environment')
def environment():
    return jsonify(setup_status)

@app.route(PREFIX+'upload',methods=['POST'])
def upload():
    if not setup_status['ready']:return jsonify(error='Environment belum siap; ulangi setup Colab'),503
    if 'project' not in request.files:return jsonify(error='Tidak ada file ZIP'),400
    if request.form.get('trusted')!='yes':return jsonify(error='Konfirmasi ZIP tepercaya wajib diberikan'),400
    mode=request.form.get('mode','auto')
    if mode not in ('auto','gpu','cpu'):return jsonify(error='Mode render tidak valid'),400
    file=request.files['project']
    if not file.filename.lower().endswith('.zip'):return jsonify(error='File harus ZIP'),400
    # Lock mencegah dua job berjalan bersamaan, termasuk saat tahap upload.
    with lock:
        if state['state'] in ('uploading','extracting','validating','installing','compositions','rendering'):
            return jsonify(error='Render sebelumnya masih berjalan'),409
        state.update(state='uploading',stage='Menerima ZIP',percent=3,frames='',message='Mengupload project',output=None,requested_mode=mode,encoder='Belum render')
        state.update(render_percent=0,fps=0,eta_seconds=None,elapsed_seconds=0,total_frames=0,current_frame=0)
        state['logs'].clear()
    try:
        zfile=UPLOAD_DIR/'incoming.zip'
        file.save(zfile)
        if zfile.stat().st_size>MAX_ZIP:raise ValueError('ZIP melebihi 50 MB')
        if not zipfile.is_zipfile(zfile):raise ValueError('File bukan ZIP yang valid')
        log('[UPLOAD] '+secure_filename(file.filename)+' diterima')
        threading.Thread(target=render_job,args=(zfile,mode),daemon=True).start()
        return jsonify(ok=True)
    except Exception as e:
        update('Upload gagal',None,'error',str(e));return jsonify(error=str(e)),400

@app.route(PREFIX+'video')
def video():
    with lock: out=state['output']
    if not out or not Path(out).exists():abort(404)
    return send_file(out,mimetype='video/mp4',conditional=True)

@app.route(PREFIX+'download')
def download():
    with lock: out=state['output']
    if not out or not Path(out).exists():abort(404)
    return send_file(out,as_attachment=True,download_name='reels_video.mp4',mimetype='video/mp4')

# Mulai server di background
threading.Thread(target=lambda:app.run(host='127.0.0.1',port=PORT,threaded=True,use_reloader=False),daemon=True).start()
time.sleep(2)

# Quick Tunnel tanpa akun/token/domain. HOME bersih agar konfigurasi lama tidak mengganggu.
print('🌐 Membuka Cloudflare Quick Tunnel...')
cf_env={**os.environ,'HOME':str(BASE_DIR/'cloudflared-home')}
Path(cf_env['HOME']).mkdir(parents=True,exist_ok=True)
tunnel=subprocess.Popen(['cloudflared','tunnel','--no-autoupdate','--url',f'http://127.0.0.1:{PORT}'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,env=cf_env)
urlpat=re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')
found={'url':None}
def read_tunnel():
    for ln in tunnel.stdout:
        print('[Tunnel]',ln.strip()[:220],flush=True)
        m=urlpat.search(ln)
        if m:found['url']=m.group(0)
threading.Thread(target=read_tunnel,daemon=True).start()
for i in range(45):
    if found['url']:break
    if tunnel.poll() is not None:break
    time.sleep(1)
if found['url']:
    access=found['url']+PREFIX
    print('\n✅ RENDER STUDIO AKTIF:',access)
    display(HTML('<a href="'+access+'" target="_blank" style="display:inline-flex;align-items:center;gap:10px;padding:14px 22px;background:#0b6b63;color:#fff;border-radius:10px;font:600 16px system-ui,sans-serif;text-decoration:none;box-shadow:inset 0 -4px 0 #0f1b33">▶ Buka Render Studio</a>'))
    print('⚠️ Siapa pun yang memiliki URL dapat mengakses studio. Upload hanya ZIP Remotion yang dipercaya. Jangan bagikan link publik.')
else:
    print('❌ Quick Tunnel belum memperoleh URL. Periksa log Cloudflare di atas.')
