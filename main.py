# kwiigonaBOT v2
# 個人情報・個人進行に関わるコマンドは原則エフェメラル表示。
# 共有情報（ランキング、会社情報、会社一覧、市場）は通常表示。
import os, random, sqlite3, math
from datetime import datetime, date, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands, tasks

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise RuntimeError('DISCORD_TOKEN が設定されていません。')
DB_FILE = 'kwiigona.db'
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

TOPICS = {'ゲーム実況':(1.10,1.00),'Roblox':(1.15,.95),'Minecraft':(1.12,.98),'PC・ガジェット':(.92,.88),'ゲーム解説':(.90,.82),'ゆっくり実況':(1.05,.92),'料理':(.98,1.00),'Vlog':(.90,1.02),'エンタメ':(1.08,1.08)}
SECTORS = {'ゲーム':1.08,'IT':1.06,'食品':1.00,'小売':.98,'製造':.97,'エンタメ':1.05,'運輸':.96,'エネルギー':.94}
REWARDS=[('N','普通のごま',100,0),('N','ごまクッキー',150,0),('N','ごまパン',200,0),('R','金ごま',500,1),('R','黒ごま宝石',800,1),('SR','幻のごま',2000,1),('SR','ごま王の印',5000,1),('UR','伝説のごま',20000,1)]
NEWS=[('ゲーム業界で大型タイトルが発表されました。','ゲーム',1.08),('IT業界で新技術が話題になりました。','IT',1.07),('食品原材料の価格が上昇しました。','食品',.94),('消費が活発になりました。','小売',1.05),('製造コストが上昇しました。','製造',.94),('エンタメ市場が盛り上がりました。','エンタメ',1.07),('燃料価格が上昇しました。','運輸',.95),('エネルギー需要が低下しました。','エネルギー',.95)]

def db(): return sqlite3.connect(DB_FILE)
def init_db():
    c=db(); x=c.cursor()
    x.execute('CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT NOT NULL,money INTEGER NOT NULL DEFAULT 100000,created_at TEXT NOT NULL)')
    x.execute('CREATE TABLE IF NOT EXISTS gomalog(user_id INTEGER PRIMARY KEY,last_date TEXT,streak INTEGER DEFAULT 0,max_streak INTEGER DEFAULT 0,total_claims INTEGER DEFAULT 0,total_rares INTEGER DEFAULT 0)')
    x.execute('CREATE TABLE IF NOT EXISTS collections(user_id INTEGER,item TEXT,count INTEGER DEFAULT 0,PRIMARY KEY(user_id,item))')
    x.execute('CREATE TABLE IF NOT EXISTS youtubers(user_id INTEGER PRIMARY KEY,subscribers INTEGER DEFAULT 0,views INTEGER DEFAULT 0,likes INTEGER DEFAULT 0,comments INTEGER DEFAULT 0,videos INTEGER DEFAULT 0,shorts INTEGER DEFAULT 0,revenue INTEGER DEFAULT 0,energy INTEGER DEFAULT 100,last_action TEXT)')
    x.execute('CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER,name TEXT UNIQUE,sector TEXT,cash INTEGER DEFAULT 500000,revenue INTEGER DEFAULT 0,profit INTEGER DEFAULT 0,reputation INTEGER DEFAULT 50,employees INTEGER DEFAULT 5,shares INTEGER DEFAULT 10000,share_price INTEGER DEFAULT 100,listed INTEGER DEFAULT 1,created_at TEXT)')
    x.execute('CREATE TABLE IF NOT EXISTS holdings(user_id INTEGER,company_id INTEGER,shares INTEGER DEFAULT 0,avg_price REAL DEFAULT 0,PRIMARY KEY(user_id,company_id))')
    x.execute('CREATE TABLE IF NOT EXISTS market_news(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT,headline TEXT,sector TEXT,impact REAL)')
    c.commit(); c.close()
def ensure_user(u):
    c=db(); c.execute('INSERT OR IGNORE INTO users(user_id,username,created_at) VALUES(?,?,?)',(u.id,str(u),datetime.now(timezone.utc).isoformat())); c.execute('UPDATE users SET username=? WHERE user_id=?',(str(u),u.id)); c.commit(); c.close()
def money(uid):
    c=db(); r=c.execute('SELECT money FROM users WHERE user_id=?',(uid,)).fetchone(); c.close(); return r[0] if r else 0
def change_money(uid,n):
    c=db(); c.execute('UPDATE users SET money=money+? WHERE user_id=?',(n,uid)); c.commit(); c.close()
def yen(n): return f'¥{int(n):,}'
def company(name):
    c=db(); r=c.execute('SELECT id,owner_id,name,sector,cash,revenue,profit,reputation,employees,shares,share_price,listed FROM companies WHERE lower(name)=lower(?)',(name,)).fetchone(); c.close(); return r

def yt(uid):
    c=db(); c.execute('INSERT OR IGNORE INTO youtubers(user_id) VALUES(?)',(uid,)); c.commit(); r=c.execute('SELECT subscribers,views,likes,comments,videos,shorts,revenue,energy FROM youtubers WHERE user_id=?',(uid,)).fetchone(); c.close(); return r

def weighted_reward(): return random.choices(REWARDS,weights=[45,20,15,8,5,4,2,1],k=1)[0]

@bot.tree.command(name='help',description='kwiigonaBOTの機能一覧')
async def help_cmd(i):
    e=discord.Embed(title='🤖 kwiigonaBOT',description='ゲーム・YouTuber・会社経営をまとめたBot')
    e.add_field(name='🎁 GomaLog',value='/gomalog /gomalog_rank /gomalog_collection',inline=False)
    e.add_field(name='🎥 くぃチューバー',value='/yt_start /yt_status /yt_post /yt_train',inline=False)
    e.add_field(name='📈 株・会社',value='/会社設立 /会社情報 /会社一覧 /市場 /株購入 /株売却 /ポートフォリオ /資産',inline=False)
    await i.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name='money',description='ゲーム内資金を確認')
async def money_cmd(i): ensure_user(i.user); await i.response.send_message(f'💰 現金：**{yen(money(i.user.id))}**', ephemeral=True)

@bot.tree.command(name='gomalog',description='今日のログイン報酬を受け取る')
async def gomalog(i):
    ensure_user(i.user); today=date.today().isoformat(); c=db(); x=c.cursor(); r=x.execute('SELECT last_date,streak FROM gomalog WHERE user_id=?',(i.user.id,)).fetchone()
    if r and r[0]==today: c.close(); await i.response.send_message('🎁 今日はもう受け取っています。',ephemeral=True); return
    streak=(r[1]+1) if r and r[0] and date.fromisoformat(r[0])==date.today()-timedelta(days=1) else 1
    grade,item,reward,rare=weighted_reward()
    x.execute('INSERT INTO gomalog(user_id,last_date,streak,max_streak,total_claims,total_rares) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET last_date=excluded.last_date,streak=excluded.streak,max_streak=MAX(gomalog.max_streak,excluded.streak),total_claims=gomalog.total_claims+1,total_rares=gomalog.total_rares+excluded.total_rares',(i.user.id,today,streak,streak,1,rare))
    x.execute('INSERT INTO collections(user_id,item,count) VALUES(?,?,1) ON CONFLICT(user_id,item) DO UPDATE SET count=count+1',(i.user.id,item)); c.commit(); c.close(); change_money(i.user.id,reward)
    await i.response.send_message(f'🎁 **GomaLog**\nランク：**{grade}**\n報酬：**{item}**\n獲得：**{yen(reward)}**\n🔥 連続：**{streak}日**')

@bot.tree.command(name='gomalog_rank',description='GomaLogランキング')
async def gl_rank(i):
    c=db(); rows=c.execute('SELECT user_id,total_claims,streak FROM gomalog ORDER BY total_claims DESC,streak DESC LIMIT 10').fetchall(); c.close()
    await i.response.send_message('🏆 **GomaLogランキング**\n'+('\n'.join(f'**{n}. <@{r[0]}>** — {r[1]}回 / 連続{r[2]}日' for n,r in enumerate(rows,1)) if rows else 'まだありません。'))

@bot.tree.command(name='gomalog_collection',description='GomaLogコレクション')
async def gl_collection(i):
    c=db(); rows=c.execute('SELECT item,count FROM collections WHERE user_id=? ORDER BY count DESC',(i.user.id,)).fetchall(); c.close(); await i.response.send_message('📚 **コレクション**\n'+('\n'.join(f'• {a} × {b}' for a,b in rows) if rows else 'まだありません。'))

@bot.tree.command(name='yt_start',description='くぃチューバーを開始')
async def yt_start(i): ensure_user(i.user); yt(i.user.id); await i.response.send_message('🎥 くぃチューバー開始！登録者0人からスタートです。', ephemeral=True)
@bot.tree.command(name='yt_status',description='チャンネル情報')
async def yt_status(i):
    ensure_user(i.user); r=yt(i.user.id); e=discord.Embed(title=f'🎥 {i.user.display_name} のチャンネル'); labels=['登録者','総再生','高評価','コメント','動画','Shorts','収益','体力']; vals=[f'{r[0]:,}人',f'{r[1]:,}回',f'{r[2]:,}',f'{r[3]:,}',f'{r[4]:,}',f'{r[5]:,}',yen(r[6]),f'{r[7]}/100']
    for a,b in zip(labels,vals): e.add_field(name=a,value=b)
    await i.response.send_message(embed=e, ephemeral=True)
@bot.tree.command(name='yt_post',description='動画を投稿')
@app_commands.describe(topic='動画ジャンル',shorts='Shortsかどうか')
@app_commands.choices(topic=[app_commands.Choice(name=x,value=x) for x in TOPICS])
async def yt_post(i,topic:app_commands.Choice[str],shorts:bool=False):
    ensure_user(i.user); r=yt(i.user.id); cost=10 if shorts else 20
    if r[7]<cost: await i.response.send_message('⚡ 体力不足です。/yt_train で回復してください。',ephemeral=True); return
    interest,competition=TOPICS[topic.value]; base=random.randint(50,300) if shorts else random.randint(80,500); views=max(1,int(base*interest*random.uniform(.75,1.35)/competition*(1+math.log10(r[0]+10)*.25))); likes=int(views*random.uniform(.035,.09)); comments=int(views*random.uniform(.002,.012)); subs=max(0,int(views*random.uniform(.005,.02))); rev=int(views*(.12 if shorts else .35)); c=db(); c.execute('UPDATE youtubers SET subscribers=subscribers+?,views=views+?,likes=likes+?,comments=comments+?,videos=videos+1,shorts=shorts+?,revenue=revenue+?,energy=energy-? WHERE user_id=?',(subs,views,likes,comments,int(shorts),rev,cost,i.user.id)); c.commit(); c.close(); change_money(i.user.id,rev)
    await i.response.send_message(f'🎬 **投稿完了**\nジャンル：{topic.value}\n再生：**{views:,}回**\n高評価：**{likes:,}**\nコメント：**{comments:,}**\n登録者：**+{subs:,}人**\n収益：**{yen(rev)}**', ephemeral=True)
@bot.tree.command(name='yt_train',description='制作トレーニング')
async def yt_train(i): yt(i.user.id); c=db(); c.execute('UPDATE youtubers SET energy=MIN(100,energy+30) WHERE user_id=?',(i.user.id,)); c.commit(); c.close(); await i.response.send_message('💪 体力が30回復しました。', ephemeral=True)

@bot.tree.command(name='会社設立',description='会社を設立')
@app_commands.describe(会社名='会社名',業種='業種')
@app_commands.choices(業種=[app_commands.Choice(name=x,value=x) for x in SECTORS])
async def create_company(i,会社名:str,業種:app_commands.Choice[str]):
    ensure_user(i.user)
    if not 2<=len(会社名)<=30: await i.response.send_message('会社名は2～30文字です。',ephemeral=True); return
    c=db();
    if c.execute('SELECT id FROM companies WHERE owner_id=?',(i.user.id,)).fetchone(): c.close(); await i.response.send_message('1ユーザーにつき会社は1社までです。'); return
    try: c.execute('INSERT INTO companies(owner_id,name,sector,created_at) VALUES(?,?,?,?)',(i.user.id,会社名,業種.value,datetime.now(timezone.utc).isoformat())); c.commit()
    except sqlite3.IntegrityError: c.close(); await i.response.send_message('その会社名はすでに使われています。'); return
    c.close(); await i.response.send_message(f'🏢 **{会社名}** を設立しました！\n業種：{業種.value}\n資本金：{yen(500000)}\n発行株式：10,000株\n初期株価：{yen(100)}', ephemeral=True)

@bot.tree.command(name='会社情報',description='会社情報を見る')
@app_commands.describe(会社名='会社名')
async def company_info(i,会社名:str):
    r=company(会社名)
    if not r: await i.response.send_message('会社が見つかりません。'); return
    e=discord.Embed(title=f'🏢 {r[2]}'); vals=[('業種',r[3]),('現金',yen(r[4])),('売上',yen(r[5])),('利益',yen(r[6])),('評判',f'{r[7]}/100'),('従業員',f'{r[8]}人'),('株価',yen(r[10])),('時価総額',yen(r[9]*r[10]))]
    for a,b in vals:e.add_field(name=a,value=b)
    await i.response.send_message(embed=e)

@bot.tree.command(name='会社一覧',description='会社一覧')
async def company_list(i):
    c=db(); rows=c.execute('SELECT name,sector,share_price,profit FROM companies WHERE listed=1 ORDER BY share_price DESC LIMIT 15').fetchall(); c.close(); await i.response.send_message('📈 **会社一覧**\n'+('\n'.join(f'**{n}. {r[0]}** [{r[1]}] — {yen(r[2])} / 利益 {yen(r[3])}' for n,r in enumerate(rows,1)) if rows else 'まだ会社がありません。'))

@bot.tree.command(name='株購入',description='株を購入')
@app_commands.describe(会社名='会社名',株数='購入株数')
async def buy(i,会社名:str,株数:int):
    ensure_user(i.user); r=company(会社名)
    if not r or not r[11]: await i.response.send_message('購入できる上場会社がありません。'); return
    if 株数<=0: await i.response.send_message('株数は1以上です。',ephemeral=True); return
    cost=r[10]*株数
    if money(i.user.id)<cost: await i.response.send_message(f'資金不足です。必要額：{yen(cost)}'); return
    c=db(); old=c.execute('SELECT shares,avg_price FROM holdings WHERE user_id=? AND company_id=?',(i.user.id,r[0])).fetchone();
    if old:
        ns=old[0]+株数; avg=(old[0]*old[1]+cost)/ns; c.execute('UPDATE holdings SET shares=?,avg_price=? WHERE user_id=? AND company_id=?',(ns,avg,i.user.id,r[0]))
    else:c.execute('INSERT INTO holdings(user_id,company_id,shares,avg_price) VALUES(?,?,?,?)',(i.user.id,r[0],株数,r[10]))
    c.commit(); c.close(); change_money(i.user.id,-cost); await i.response.send_message(f'🛒 **{r[2]}** を {株数:,}株購入。購入額：**{yen(cost)}**', ephemeral=True)

@bot.tree.command(name='株売却',description='保有株を売却')
@app_commands.describe(会社名='会社名',株数='売却株数')
async def sell(i,会社名:str,株数:int):
    ensure_user(i.user); r=company(会社名)
    if not r or 株数<=0: await i.response.send_message('会社または株数が不正です。',ephemeral=True); return
    c=db(); h=c.execute('SELECT shares FROM holdings WHERE user_id=? AND company_id=?',(i.user.id,r[0])).fetchone()
    if not h or h[0]<株数: c.close(); await i.response.send_message('その株を十分に保有していません。'); return
    remain=h[0]-株数
    if remain:c.execute('UPDATE holdings SET shares=? WHERE user_id=? AND company_id=?',(remain,i.user.id,r[0]))
    else:c.execute('DELETE FROM holdings WHERE user_id=? AND company_id=?',(i.user.id,r[0]))
    c.commit(); c.close(); proceeds=r[10]*株数; change_money(i.user.id,proceeds); await i.response.send_message(f'💵 **{r[2]}** を {株数:,}株売却。売却額：**{yen(proceeds)}**', ephemeral=True)

@bot.tree.command(name='ポートフォリオ',description='保有株を確認')
async def portfolio(i):
    ensure_user(i.user); c=db(); rows=c.execute('SELECT c.name,h.shares,c.share_price,h.avg_price FROM holdings h JOIN companies c ON c.id=h.company_id WHERE h.user_id=? AND h.shares>0',(i.user.id,)).fetchall(); c.close()
    if not rows: await i.response.send_message('保有株はありません。', ephemeral=True); return
    total=sum(s*p for _,s,p,_ in rows); lines=[f'**{n}** — {s:,}株 / {yen(s*p)} / 損益 {yen((p-a)*s)}' for n,s,p,a in rows]; await i.response.send_message('📊 **ポートフォリオ**\n'+'\n'.join(lines)+f'\n\n株式評価額：**{yen(total)}**\n現金：**{yen(money(i.user.id))}**', ephemeral=True)

@bot.tree.command(name='市場',description='市場情報を見る')
async def market(i):
    c=db(); rows=c.execute('SELECT name,share_price,profit FROM companies ORDER BY share_price DESC LIMIT 10').fetchall(); news=c.execute('SELECT headline FROM market_news ORDER BY id DESC LIMIT 3').fetchall(); c.close(); text='📈 **KwiiMarket 市場**\n'+('\n'.join(f'• {a} — {yen(b)} / 利益 {yen(d)}' for a,b,d in rows) if rows else 'まだ会社がありません。');
    if news:text+='\n\n📰 **ニュース**\n'+'\n'.join('• '+x[0] for x in news)
    await i.response.send_message(text)

@bot.tree.command(name='資産',description='総資産を確認')
async def assets(i):
    ensure_user(i.user); c=db(); r=c.execute('SELECT COALESCE(SUM(h.shares*c.share_price),0) FROM holdings h JOIN companies c ON c.id=h.company_id WHERE h.user_id=?',(i.user.id,)).fetchone(); c.close(); cash=money(i.user.id); stocks=r[0] or 0; await i.response.send_message(f'💰 **総資産**\n現金：{yen(cash)}\n株式：{yen(stocks)}\n**合計：{yen(cash+stocks)}**', ephemeral=True)

@tasks.loop(hours=6)
async def market_tick():
    c=db(); companies=c.execute('SELECT id,sector,share_price,cash,revenue,profit,reputation,employees FROM companies').fetchall()
    if not companies:c.close();return
    headline,sector,mult=random.choice(NEWS); c.execute('INSERT INTO market_news(created_at,headline,sector,impact) VALUES(?,?,?,?)',(datetime.now(timezone.utc).isoformat(),headline,sector,mult))
    for cid,sec,price,cash,rev,profit,rep,emp in companies:
        sm=mult if sec==sector else random.uniform(.985,1.015); sales=max(1000,int(emp*random.randint(5000,12000)*sm)); expense=int(sales*random.uniform(.65,.92)); dp=sales-expense; np=max(0,cash+dp); nr=rev+sales; nprofit=profit+dp; nrep=max(1,min(100,rep+(1 if dp>0 else -1))); perf=1+max(-.08,min(.08,dp/1_000_000)); npice=max(1,min(1_000_000,int(price*sm*random.uniform(.96,1.04)*perf))); c.execute('UPDATE companies SET cash=?,revenue=?,profit=?,reputation=?,share_price=? WHERE id=?',(np,nr,nprofit,nrep,npice,cid))
    c.commit();c.close()

@bot.event
async def on_ready():
    init_db()
    try: print(f'同期: {len(await bot.tree.sync())} コマンド')
    except Exception as e: print('同期エラー:',e)
    if not market_tick.is_running(): market_tick.start()
    print('ログイン:',bot.user)

init_db()
bot.run(TOKEN)
