# kwiigonaBOT v8
# Botの返信はすべてエフェメラル（実行者本人のみ表示）。
# 会社削除・チャンネル削除を追加。
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
    e.add_field(name='📈 株・会社',value='/会社設立 /会社情報 /会社一覧 /市場 /株購入 /株売却 /ポートフォリオ /資産 /会社削除',inline=False)
    e.add_field(name='🔄 リセット',value='/チャンネル削除（自分のチャンネルを削除）',inline=False)
    e.add_field(name='⚔️ Battle',value='/battle /battle質問 /battle回答 /battle推理 /battle降参 /battleアイテム /battleステータス /battleランキング /battleランダム /battleランクマッチ /battleキャンセル',inline=False)
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
    x.execute('INSERT INTO collections(user_id,item,count) VALUES(?,?,1) ON CONFLICT(user_id,item) DO UPDATE SET count=count+1',(i.user.id,item)); c.commit(); c.close();
    ensure_economies(i.user.id); add_gomalog_points(i.user.id,reward)
    await i.response.send_message(f'🎁 **GomaLog**\nランク：**{grade}**\n報酬：**{item}**\n獲得：**{yen(reward)}**\n🔥 連続：**{streak}日**', ephemeral=True)

@bot.tree.command(name='gomalog_rank',description='GomaLogランキング')
async def gl_rank(i):
    c=db(); rows=c.execute('SELECT user_id,total_claims,streak FROM gomalog ORDER BY total_claims DESC,streak DESC LIMIT 10').fetchall(); c.close()
    await i.response.send_message('🏆 **GomaLogランキング**\n'+('\n'.join(f'**{n}. <@{r[0]}>** — {r[1]}回 / 連続{r[2]}日' for n,r in enumerate(rows,1)) if rows else 'まだありません。'), ephemeral=True)

@bot.tree.command(name='gomalog_collection',description='GomaLogコレクション')
async def gl_collection(i):
    c=db(); rows=c.execute('SELECT item,count FROM collections WHERE user_id=? ORDER BY count DESC',(i.user.id,)).fetchall(); c.close(); await i.response.send_message('📚 **コレクション**\n'+('\n'.join(f'• {a} × {b}' for a,b in rows) if rows else 'まだありません。'), ephemeral=True)

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
    if c.execute('SELECT id FROM companies WHERE owner_id=?',(i.user.id,)).fetchone(): c.close(); await i.response.send_message('1ユーザーにつき会社は1社までです。', ephemeral=True); return
    try: c.execute('INSERT INTO companies(owner_id,name,sector,created_at) VALUES(?,?,?,?)',(i.user.id,会社名,業種.value,datetime.now(timezone.utc).isoformat())); c.commit()
    except sqlite3.IntegrityError: c.close(); await i.response.send_message('その会社名はすでに使われています。', ephemeral=True); return
    c.close(); await i.response.send_message(f'🏢 **{会社名}** を設立しました！\n業種：{業種.value}\n資本金：{yen(500000)}\n発行株式：10,000株\n初期株価：{yen(100)}', ephemeral=True)

@bot.tree.command(name='会社情報',description='会社情報を見る')
@app_commands.describe(会社名='会社名')
async def company_info(i,会社名:str):
    r=company(会社名)
    if not r: await i.response.send_message('会社が見つかりません。', ephemeral=True); return
    e=discord.Embed(title=f'🏢 {r[2]}'); vals=[('業種',r[3]),('現金',yen(r[4])),('売上',yen(r[5])),('利益',yen(r[6])),('評判',f'{r[7]}/100'),('従業員',f'{r[8]}人'),('株価',yen(r[10])),('時価総額',yen(r[9]*r[10]))]
    for a,b in vals:e.add_field(name=a,value=b)
    await i.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name='会社一覧',description='会社一覧')
async def company_list(i):
    c=db(); rows=c.execute('SELECT name,sector,share_price,profit FROM companies WHERE listed=1 ORDER BY share_price DESC LIMIT 15').fetchall(); c.close(); await i.response.send_message('📈 **会社一覧**\n'+('\n'.join(f'**{n}. {r[0]}** [{r[1]}] — {yen(r[2])} / 利益 {yen(r[3])}' for n,r in enumerate(rows,1)) if rows else 'まだ会社がありません。'), ephemeral=True)

@bot.tree.command(name='株購入',description='株を購入')
@app_commands.describe(会社名='会社名',株数='購入株数')
async def buy(i,会社名:str,株数:int):
    ensure_user(i.user); r=company(会社名)
    if not r or not r[11]: await i.response.send_message('購入できる上場会社がありません。', ephemeral=True); return
    if 株数<=0: await i.response.send_message('株数は1以上です。',ephemeral=True); return
    cost=r[10]*株数
    if money(i.user.id)<cost: await i.response.send_message(f'資金不足です。必要額：{yen(cost)}', ephemeral=True); return
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
    if not h or h[0]<株数: c.close(); await i.response.send_message('その株を十分に保有していません。', ephemeral=True); return
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
    await i.response.send_message(text, ephemeral=True)

@bot.tree.command(name='資産',description='総資産を確認')
async def assets(i):
    ensure_user(i.user); c=db(); r=c.execute('SELECT COALESCE(SUM(h.shares*c.share_price),0) FROM holdings h JOIN companies c ON c.id=h.company_id WHERE h.user_id=?',(i.user.id,)).fetchone(); c.close(); cash=money(i.user.id); stocks=r[0] or 0; ensure_battle_profile(i.user.id); c=db(); br=c.execute('SELECT battle_points FROM battle_profiles WHERE user_id=?',(i.user.id,)).fetchone(); c.close(); bp=br[0] if br else 0; await i.response.send_message(
        f"💰 **総合資産**\n"
        f"🎥 YouTube資金：**{yen(youtube_money(i.user.id))}**\n"
        f"🏢 会社・株式：**{yen(cash+stocks)}**\n"
        f"🎁 GomaLogポイント：**{gomalog_points(i.user.id)}**\n"
        f"⚔️ Battle Point：**{bp}**",
        ephemeral=True
    )


@bot.tree.command(name='会社削除',description='自分の会社を削除')
async def delete_company(i):
    ensure_user(i.user)
    c=db()
    r=c.execute('SELECT id,name,share_price FROM companies WHERE owner_id=?',(i.user.id,)).fetchone()
    if not r:
        c.close()
        await i.response.send_message('🏢 あなたが所有する会社はありません。', ephemeral=True)
        return
    cid,name,price=r
    # Current shareholders are bought out at the current market price before deletion.
    holders=c.execute('SELECT user_id,shares FROM holdings WHERE company_id=? AND shares>0',(cid,)).fetchall()
    refund=sum(uid_shares[1]*price for uid_shares in holders)
    for uid,shares in holders:
        c.execute('UPDATE users SET money=money+? WHERE user_id=?',(shares*price,uid))
    c.execute('DELETE FROM holdings WHERE company_id=?',(cid,))
    c.execute('DELETE FROM companies WHERE id=?',(cid,))
    c.commit(); c.close()
    await i.response.send_message(
        f'🗑️ **{name}** を削除しました。\n'
        f'保有者には現在株価 **{yen(price)}** で自動精算しました。\n'
        f'精算総額：**{yen(refund)}**',
        ephemeral=True
    )

@bot.tree.command(name='チャンネル削除',description='自分のくぃチューバーチャンネルを削除')
async def delete_channel(i):
    ensure_user(i.user)
    c=db()
    r=c.execute('SELECT subscribers,views,videos FROM youtubers WHERE user_id=?',(i.user.id,)).fetchone()
    if not r:
        c.close()
        await i.response.send_message('🎥 あなたのくぃチューバーチャンネルはありません。', ephemeral=True)
        return
    c.execute('DELETE FROM youtubers WHERE user_id=?',(i.user.id,))
    c.commit(); c.close()
    await i.response.send_message(
        '🗑️ **くぃチューバーチャンネルを削除しました。**\n'
        '登録者・再生数・動画数・収益などのチャンネル進行をリセットしました。',
        ephemeral=True
    )



# =========================
# 💰 Separate Game Economies
# =========================
# YouTube money, company money, and GomaLog points are kept separate.
# Battle Points are already stored separately in battle_profiles.

def init_separate_economies():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS youtube_wallets(
        user_id INTEGER PRIMARY KEY,
        balance INTEGER NOT NULL DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS gomalog_wallets(
        user_id INTEGER PRIMARY KEY,
        points INTEGER NOT NULL DEFAULT 0
    )""")
    # Company/stock cash is stored in the existing users.money field.
    c.commit()
    c.close()

def ensure_economies(user_id):
    c = db()
    c.execute("INSERT OR IGNORE INTO youtube_wallets(user_id) VALUES(?)", (user_id,))
    c.execute("INSERT OR IGNORE INTO gomalog_wallets(user_id) VALUES(?)", (user_id,))
    c.commit()
    c.close()

def youtube_money(user_id):
    ensure_economies(user_id)
    c = db()
    r = c.execute("SELECT balance FROM youtube_wallets WHERE user_id=?", (user_id,)).fetchone()
    c.close()
    return r[0] if r else 0

def add_youtube_money(user_id, amount):
    ensure_economies(user_id)
    c = db()
    c.execute("UPDATE youtube_wallets SET balance=MAX(0,balance+?) WHERE user_id=?", (amount,user_id))
    c.commit()
    c.close()

def gomalog_points(user_id):
    ensure_economies(user_id)
    c = db()
    r = c.execute("SELECT points FROM gomalog_wallets WHERE user_id=?", (user_id,)).fetchone()
    c.close()
    return r[0] if r else 0

def add_gomalog_points(user_id, amount):
    ensure_economies(user_id)
    c = db()
    c.execute("UPDATE gomalog_wallets SET points=MAX(0,points+?) WHERE user_id=?", (amount,user_id))
    c.commit()
    c.close()

init_separate_economies()

# =========================
# ⚔️ kwiigonaBOT Battle v8
# 「アキネーター風」の対人推理バトル。
# お題はBotが自動選択し、プレイヤー同士で質問・回答・推理を行う。
# =========================

BATTLE_TOPIC_DATA = {
    "食べ物": ["りんご","バナナ","カレー","ラーメン","ピザ","アイス","寿司","ハンバーガー","ケーキ","おにぎり"],
    "動物": ["猫","犬","ペンギン","イルカ","ライオン","パンダ","うさぎ","キリン","ゾウ","カメ"],
    "乗り物": ["自転車","電車","新幹線","飛行機","船","バス","タクシー","バイク","ヘリコプター","ロケット"],
    "電子機器": ["スマートフォン","パソコン","テレビ","カメラ","イヤホン","ゲーム機","タブレット","スマートウォッチ","キーボード","マウス"],
    "場所": ["学校","病院","コンビニ","映画館","公園","駅","空港","図書館","遊園地","水族館"],
    "日用品": ["傘","時計","リュック","財布","眼鏡","ペン","ノート","椅子","机","リモコン"],
    "趣味・娯楽": ["映画","ゲーム","漫画","小説","ギター","サッカーボール","トランプ","カラオケ","写真","プラモデル"],
    "自然・科学": ["海","山","太陽","月","星","宇宙","火山","雪","雲","虹"],
    "ファンタジー": ["ドラゴン","魔法使い","妖精","勇者","魔法の杖","モンスター","城","宝箱","宇宙人","ロボット"],
}
BATTLE_TOPICS = [x for group in BATTLE_TOPIC_DATA.values() for x in group]
BATTLE_TOPIC_CATEGORY = {topic: category for category, items in BATTLE_TOPIC_DATA.items() for topic in items}

BATTLE_ITEM_POOL = [
    ("攻撃", "追加質問カード"),
    ("攻撃", "ヒントカード"),
    ("攻撃", "回答強制カード"),
    ("防御", "ガードカード"),
    ("防御", "質問変更カード"),
    ("防御", "情報隠蔽カード"),
]
BATTLE_ITEM_CHOICES = [app_commands.Choice(name=n, value=n) for _, n in BATTLE_ITEM_POOL]

BATTLE_RANKS = [
    ("Bronze", 0), ("Silver", 800), ("Gold", 1100),
    ("Platinum", 1400), ("Diamond", 1700), ("Master", 2000),
    ("Grand Master", 2300),
]

def battle_rank(rating):
    result = BATTLE_RANKS[0][0]
    for name, threshold in BATTLE_RANKS:
        if rating >= threshold:
            result = name
    return result

def init_battle_tables():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS battle_profiles(
        user_id INTEGER PRIMARY KEY,
        rating INTEGER NOT NULL DEFAULT 1000,
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,
        streak INTEGER NOT NULL DEFAULT 0,
        best_streak INTEGER NOT NULL DEFAULT 0,
        battle_points INTEGER NOT NULL DEFAULT 0,
        total_games INTEGER NOT NULL DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS battle_items(
        user_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        item_type TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(user_id,item_name)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS battle_matches(
        match_id TEXT PRIMARY KEY,
        player1 INTEGER NOT NULL,
        player2 INTEGER NOT NULL,
        player1_topic TEXT,
        player2_topic TEXT,
        turn_user INTEGER,
        status TEXT NOT NULL DEFAULT 'waiting',
        player1_questions INTEGER NOT NULL DEFAULT 0,
        player2_questions INTEGER NOT NULL DEFAULT 0,
        winner INTEGER,
        created_at TEXT NOT NULL,
        last_question TEXT,
        last_question_from INTEGER,
        extra_question_user INTEGER,
        forced_unknown_user INTEGER,
        hidden_hint_user INTEGER,
        pending_change_user INTEGER,
        force_binary_user INTEGER,
        total_questions INTEGER NOT NULL DEFAULT 0,
        player1_unknowns INTEGER NOT NULL DEFAULT 0,
        player2_unknowns INTEGER NOT NULL DEFAULT 0
    )""")
    # v6/v7 の既存DBから安全に移行。
    existing = {row[1] for row in c.execute("PRAGMA table_info(battle_matches)").fetchall()}
    migrations = {
        "questioner": "INTEGER",
        "answerer": "INTEGER",
        "answerer_topic": "TEXT",
        "last_question": "TEXT",
        "last_question_from": "INTEGER",
        "extra_question_user": "INTEGER",
        "forced_unknown_user": "INTEGER",
        "hidden_hint_user": "INTEGER",
        "pending_change_user": "INTEGER",
        "force_binary_user": "INTEGER",
        "total_questions": "INTEGER NOT NULL DEFAULT 0",
        "player1_unknowns": "INTEGER NOT NULL DEFAULT 0",
        "player2_unknowns": "INTEGER NOT NULL DEFAULT 0",
    }
    for col, definition in migrations.items():
        if col not in existing:
            c.execute(f"ALTER TABLE battle_matches ADD COLUMN {col} {definition}")
    # 旧Battleが残っている場合も新しい役割方式へ移行。
    c.execute("""UPDATE battle_matches
                 SET questioner=COALESCE(questioner,player1),
                     answerer=COALESCE(answerer,player2),
                     answerer_topic=COALESCE(answerer_topic,player2_topic)
                 WHERE questioner IS NULL OR answerer IS NULL OR answerer_topic IS NULL""")
    c.execute("""CREATE TABLE IF NOT EXISTS battle_invites(
        invite_id TEXT PRIMARY KEY,
        inviter INTEGER NOT NULL,
        invitee INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS battle_queue(
        user_id INTEGER PRIMARY KEY,
        server_id INTEGER NOT NULL,
        queued_at TEXT NOT NULL,
        ranked INTEGER NOT NULL DEFAULT 0
    )""")
    existing_q = {row[1] for row in c.execute("PRAGMA table_info(battle_queue)").fetchall()}
    if "ranked" not in existing_q:
        c.execute("ALTER TABLE battle_queue ADD COLUMN ranked INTEGER NOT NULL DEFAULT 0")
    c.commit()
    c.close()

def ensure_battle_profile(user_id):
    c = db()
    c.execute("INSERT OR IGNORE INTO battle_profiles(user_id) VALUES(?)", (user_id,))
    c.commit()
    c.close()

def give_battle_item(user_id):
    item_type, item_name = random.choice(BATTLE_ITEM_POOL)
    c = db()
    c.execute("""INSERT INTO battle_items(user_id,item_name,item_type,quantity)
                 VALUES(?,?,?,1)
                 ON CONFLICT(user_id,item_name) DO UPDATE SET quantity=quantity+1""",
              (user_id,item_name,item_type))
    c.commit(); c.close()
    return item_type, item_name

def consume_battle_item(user_id, item_name):
    c = db()
    r = c.execute("SELECT item_type,quantity FROM battle_items WHERE user_id=? AND item_name=?", (user_id,item_name)).fetchone()
    if not r or r[1] <= 0:
        c.close(); return None
    c.execute("UPDATE battle_items SET quantity=quantity-1 WHERE user_id=? AND item_name=?", (user_id,item_name))
    c.commit(); c.close()
    return r[0]

def battle_change_rating(winner_id, loser_id):
    c = db()
    w = c.execute("SELECT rating FROM battle_profiles WHERE user_id=?", (winner_id,)).fetchone()
    l = c.execute("SELECT rating FROM battle_profiles WHERE user_id=?", (loser_id,)).fetchone()
    wr, lr = (w[0] if w else 1000), (l[0] if l else 1000)
    expected_w = 1 / (1 + 10 ** ((lr - wr) / 400))
    delta = max(10, min(32, round(24 * (1 - expected_w) + 10)))
    c.execute("""UPDATE battle_profiles SET rating=rating+?, wins=wins+1,
                 total_games=total_games+1, streak=streak+1,
                 best_streak=MAX(best_streak,streak+1), battle_points=battle_points+100
                 WHERE user_id=?""", (delta,winner_id))
    c.execute("""UPDATE battle_profiles SET rating=MAX(0,rating-?), losses=losses+1,
                 total_games=total_games+1, streak=0, battle_points=MAX(0,battle_points+30)
                 WHERE user_id=?""", (delta,loser_id))
    c.commit(); c.close()
    return delta

def battle_get_active(user_id):
    c = db()
    r = c.execute("""SELECT * FROM battle_matches
                    WHERE (player1=? OR player2=?) AND status='active'
                    ORDER BY created_at DESC LIMIT 1""", (user_id,user_id)).fetchone()
    c.close()
    return r

def battle_other(match, user_id):
    return match[2] if match[1] == user_id else match[1]

def battle_topic_for(match, user_id):
    # お題は回答者のものだけ。質問者から見た「相手のお題」を返す。
    if len(match) > 23 and match[23]:
        return match[23]
    answerer = match[22] if len(match) > 22 and match[22] else match[2]
    return match[4] if answerer == match[2] else match[3]

init_battle_tables()

@bot.tree.command(name='battle', description='友達に推理バトルを招待する')
@app_commands.describe(相手='対戦する相手')
async def battle_start(i, 相手: discord.Member):
    ensure_battle_profile(i.user.id); ensure_battle_profile(相手.id)
    if 相手.id == i.user.id:
        await i.response.send_message("⚔️ 自分自身とは対戦できません。", ephemeral=True); return
    if 相手.bot:
        await i.response.send_message("🤖 Botとは対戦できません。", ephemeral=True); return
    if battle_get_active(i.user.id) or battle_get_active(相手.id):
        await i.response.send_message("⚔️ どちらかがすでにBattle中です。", ephemeral=True); return

    c = db()
    # 同じ2人の保留中招待を確認。INSERT側にもUNIQUE INDEXを入れて競合時も二重作成を防ぐ。
    existing = c.execute("SELECT invite_id FROM battle_invites WHERE status='pending' AND ((inviter=? AND invitee=?) OR (inviter=? AND invitee=?)) LIMIT 1", (i.user.id, 相手.id, 相手.id, i.user.id)).fetchone()
    if existing:
        c.close()
        await i.response.send_message("📨 すでにその相手へのBattle招待が保留中です。", ephemeral=True); return
    invite_id = f"I{i.id}"
    try:
        c.execute("INSERT INTO battle_invites(invite_id,inviter,invitee,status,created_at) VALUES(?,?,?,?,?)",
                  (invite_id,i.user.id,相手.id,'pending',datetime.now(timezone.utc).isoformat()))
        c.commit()
    except sqlite3.IntegrityError:
        c.close()
        await i.response.send_message("📨 すでにその相手へのBattle招待が保留中です。", ephemeral=True)
        return
    c.close()

    view = BattleInviteView(invite_id, i.user.id, 相手.id)
    try:
        await 相手.send(
            f"⚔️ **Battleへの招待が届きました！**\n"
            f"招待者：**{i.user.display_name}**\n\n"
            f"参加するなら **承認**、対戦したくないなら **拒否** を押してください。\n"
            f"⏱️ この招待は10分で期限切れになります。",
            view=view
        )
        await i.response.send_message(
            f"📨 **Battle招待を送りました！**\n相手：**{相手.display_name}**\n"
            f"相手が承認するとBattleが開始されます。",
            ephemeral=True)
    except Exception:
        c = db(); c.execute("UPDATE battle_invites SET status='cancelled' WHERE invite_id=?", (invite_id,)); c.commit(); c.close()
        await i.response.send_message("❌ 相手にDMを送れませんでした。相手のDM設定を確認してください。", ephemeral=True)


class BattleInviteView(discord.ui.View):
    def __init__(self, invite_id, inviter_id, invitee_id):
        super().__init__(timeout=600)
        self.invite_id = invite_id
        self.inviter_id = inviter_id
        self.invitee_id = invitee_id
        # ボタンを明示的に作成して、承認/拒否の処理が入れ替わらないようにする。
        self.accept_button = BattleInviteAcceptButton(self)
        self.reject_button = BattleInviteRejectButton(self)
        self.delete_button = BattleInviteDeleteButton(self)
        self.delete_button.disabled = True
        self.add_item(self.accept_button)
        self.add_item(self.reject_button)
        self.add_item(self.delete_button)

    async def finish_invite(self, interaction, accepted: bool):
        if interaction.user.id != self.invitee_id:
            await interaction.response.send_message("❌ この招待を操作できるのは招待された本人だけです。", ephemeral=True)
            return

        c = db()
        row = c.execute("SELECT status FROM battle_invites WHERE invite_id=?", (self.invite_id,)).fetchone()
        if not row or row[0] != 'pending':
            c.close()
            await interaction.response.send_message("⚠️ この招待はすでに処理済み、または期限切れです。", ephemeral=True)
            return

        if not accepted:
            cur = c.execute("UPDATE battle_invites SET status='rejected' WHERE invite_id=? AND status='pending'", (self.invite_id,))
            if cur.rowcount != 1:
                c.rollback()
                c.close()
                await interaction.response.send_message("⚠️ この招待は別の処理によって確定しました。", ephemeral=True)
                return
            c.commit()
            c.close()
            self.accept_button.disabled = True
            self.reject_button.disabled = True
            self.delete_button.disabled = False
            await interaction.response.edit_message(content="🚫 **Battle招待を拒否しました。**\nこの対戦は開始されません。\n\n🗑️ メッセージを消す場合は下のボタンを押してください。", view=self)
            try:
                inviter = await bot.fetch_user(self.inviter_id)
                await inviter.send(f"🚫 **{interaction.user.display_name}** がBattle招待を拒否しました。")
            except Exception:
                pass
            return

        c = db()
        if battle_get_active(self.inviter_id) or battle_get_active(self.invitee_id):
            c.execute("UPDATE battle_invites SET status='cancelled' WHERE invite_id=? AND status='pending'", (self.invite_id,))
            c.commit()
            c.close()
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(content="⚠️ どちらかがすでにBattle中のため、開始できませんでした。", view=self)
            return

        match_id = f"B{random.randrange(0x1000000):06X}"
        questioner, answerer = random.sample([self.inviter_id, self.invitee_id], 2)
        answerer_topic = random.choice(BATTLE_TOPICS)
        c.execute("""INSERT INTO battle_matches
            (match_id,player1,player2,player1_topic,player2_topic,questioner,answerer,answerer_topic,turn_user,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (match_id,self.inviter_id,self.invitee_id,None,None,questioner,answerer,answerer_topic,questioner,'active',datetime.now(timezone.utc).isoformat()))
        cur = c.execute("UPDATE battle_invites SET status='accepted' WHERE invite_id=? AND status='pending'", (self.invite_id,))
        if cur.rowcount != 1:
            c.rollback()
            c.close()
            await interaction.response.send_message("⚠️ この招待は別の処理によって確定しました。", ephemeral=True)
            return
        c.commit()
        c.close()

        self.accept_button.disabled = True
        self.reject_button.disabled = True
        self.delete_button.disabled = False
        await interaction.response.edit_message(content="✅ **Battle招待を承認しました！Battle開始！**\n\n🗑️ メッセージを消す場合は下のボタンを押してください。", view=self)
        q_user = await bot.fetch_user(questioner)
        a_user = await bot.fetch_user(answerer)
        try:
            await q_user.send(f"⚔️ **Battle開始！**\n対戦相手：**{a_user.display_name}**\n対戦ID：`{match_id}`\n\n❓ **あなたは質問者です！**\n相手のお題を20問以内に当ててください。\n`/battle質問` で質問、`/battle推理` で推理できます。")
            await a_user.send(f"⚔️ **Battle開始！**\n対戦相手：**{q_user.display_name}**\n対戦ID：`{match_id}`\n\n🧠 **あなたは回答者です！**\n🔐 お題：**{answerer_topic}**\n質問されたら `/battle回答` で YES / NO / わからない と答えてください。\n🤔『わからない』は3回までです。")
        except Exception:
            pass

    async def on_timeout(self):
        c = db()
        c.execute("UPDATE battle_invites SET status='expired' WHERE invite_id=? AND status='pending'", (self.invite_id,))
        c.commit()
        c.close()
        for child in self.children:
            child.disabled = True
        try:
            if self.message:
                await self.message.edit(content="⌛ **Battle招待の期限が切れました。**", view=self)
        except Exception:
            pass


class BattleInviteAcceptButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(label='承認', style=discord.ButtonStyle.success, emoji='✅')
        self.invite_view = view

    async def callback(self, interaction: discord.Interaction):
        await self.invite_view.finish_invite(interaction, True)


class BattleInviteDeleteButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(label='このメッセージを削除', style=discord.ButtonStyle.secondary, emoji='🗑️', row=1)
        self.invite_view = view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invite_view.invitee_id:
            await interaction.response.send_message("❌ この招待メッセージを削除できるのは招待された本人だけです。", ephemeral=True)
            return
        c = db()
        row = c.execute("SELECT status FROM battle_invites WHERE invite_id=?", (self.invite_view.invite_id,)).fetchone()
        c.close()
        if not row or row[0] not in ('accepted', 'rejected'):
            await interaction.response.send_message("⚠️ 先に承認または拒否を選択してください。", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except Exception:
            pass


class BattleInviteRejectButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(label='拒否', style=discord.ButtonStyle.danger, emoji='🚫')
        self.invite_view = view

    async def callback(self, interaction: discord.Interaction):
        await self.invite_view.finish_invite(interaction, False)


@bot.tree.command(name='battle質問', description='相手のお題を推理する質問を送る')
@app_commands.describe(質問='YES/NOで答えられる質問がおすすめです')
async def battle_question(i, 質問: str):
    match = battle_get_active(i.user.id)
    if not match:
        await i.response.send_message("⚔️ 現在参加中のBattleはありません。", ephemeral=True); return
    questioner = match[21] if len(match) > 21 and match[21] else match[1]
    answerer = match[22] if len(match) > 22 and match[22] else match[2]
    if i.user.id != questioner:
        await i.response.send_message("🧠 あなたは**回答者**です。相手から質問が来たら `/battle回答` で答えてください。", ephemeral=True); return
    if match[11] and match[12] != i.user.id:
        pass
    if match[11]:
        await i.response.send_message("⏳ まだ前の質問への回答待ちです。", ephemeral=True); return
    if len(質問.strip()) < 1 or len(質問) > 120:
        await i.response.send_message("❌ 質問は1～120文字です。", ephemeral=True); return
    total_q = match[7] + match[8]
    if total_q >= 20:
        await i.response.send_message("❌ このBattleの質問回数は20問までです。", ephemeral=True); return
    c = db()
    if match[1] == i.user.id:
        c.execute("UPDATE battle_matches SET player1_questions=player1_questions+1,total_questions=total_questions+1,turn_user=?,last_question=?,last_question_from=? WHERE match_id=?", (answerer,i.user.id,質問.strip(),i.user.id,match[0]))
    else:
        c.execute("UPDATE battle_matches SET player2_questions=player2_questions+1,total_questions=total_questions+1,turn_user=?,last_question=?,last_question_from=? WHERE match_id=?", (answerer,i.user.id,質問.strip(),i.user.id,match[0]))
    c.commit(); c.close()
    await i.response.send_message(f"❓ 質問を送信しました。\n> {質問.strip()}\n\n🧠 回答者の回答を待っています。", ephemeral=True)
    try:
        await (await bot.fetch_user(answerer)).send(f"⚔️ **Battle `{match[0]}`**\n❓ 相手から質問です：\n> {質問.strip()}\n\n`/battle回答` で **YES / NO / わからない** を選んでください。\n🤔『わからない』は残り3回までです。")
    except Exception:
        pass

@bot.tree.command(name='battle回答', description='相手からの質問に答える')
@app_commands.choices(回答=[
    app_commands.Choice(name='YES',value='YES'),
    app_commands.Choice(name='NO',value='NO'),
    app_commands.Choice(name='わからない',value='UNKNOWN')])
async def battle_answer(i, 回答: app_commands.Choice[str]):
    match = battle_get_active(i.user.id)
    if not match:
        await i.response.send_message("⚔️ 現在参加中のBattleはありません。", ephemeral=True); return
    answerer = match[22] if len(match) > 22 and match[22] else match[2]
    questioner = match[21] if len(match) > 21 and match[21] else match[1]
    if i.user.id != answerer:
        await i.response.send_message("❓ あなたは**質問者**です。質問を送るか、お題を推理してください。", ephemeral=True); return
    if not match[11] or match[12] != i.user.id:
        await i.response.send_message("⏳ 今は回答する質問がありません。", ephemeral=True); return

    answer = 回答.value
    forced_unknown = match[14] == i.user.id
    force_binary = match[17] == i.user.id
    if force_binary and answer == "UNKNOWN":
        await i.response.send_message("🎯 回答強制カードの効果中です。今回は **YES / NO** のどちらかを選んでください。", ephemeral=True); return
    if forced_unknown:
        answer = "UNKNOWN"
    unknowns = match[19] if match[1] == i.user.id else match[20]
    if answer == "UNKNOWN" and not forced_unknown and unknowns >= 3:
        await i.response.send_message("⚠️ この試合では『わからない』は3回までです。YES / NOで回答してください。", ephemeral=True); return
    extra = match[13] == i.user.id
    total_q = match[7] + match[8]
    c = db()
    if answer == "UNKNOWN" and not forced_unknown:
        if match[1] == i.user.id:
            c.execute("UPDATE battle_matches SET player1_unknowns=player1_unknowns+1 WHERE match_id=?", (match[0],))
        else:
            c.execute("UPDATE battle_matches SET player2_unknowns=player2_unknowns+1 WHERE match_id=?", (match[0],))
    c.execute("UPDATE battle_matches SET forced_unknown_user=NULL,force_binary_user=NULL WHERE match_id=?", (match[0],))
    if total_q >= 20:
        c.execute("UPDATE battle_matches SET status='finished',winner=? WHERE match_id=?", (i.user.id,match[0]))
        c.commit(); c.close()
        delta = battle_change_rating(i.user.id, questioner)
        item_type,item_name = give_battle_item(i.user.id)
        await i.response.send_message(f"🏁 **20問終了！**\n🧠 回答者の **{i.user.display_name}** さんの勝利です。\n🏆 **+{delta} Rating** / +100 Battle Point\n🎁 **{item_type}：{item_name}** を獲得！", ephemeral=True)
        try:
            await (await bot.fetch_user(questioner)).send(f"🏁 Battle `{match[0]}` は20問終了！\n回答者の勝利です。")
        except Exception: pass
        return
    c.execute("UPDATE battle_matches SET extra_question_user=NULL,turn_user=?,last_question=NULL,last_question_from=NULL WHERE match_id=?", (questioner,match[0]))
    c.commit(); c.close()
    shown = 'わからない' if answer == 'UNKNOWN' else answer
    await i.response.send_message(f"📨 **{shown}** と回答しました。", ephemeral=True)
    try:
        await (await bot.fetch_user(questioner)).send(f"📨 Battle `{match[0]}`\n質問への回答：**{shown}**\n⏭️ 次はあなたのターンです。残り質問：**{20-(total_q)}問**")
    except Exception: pass

@bot.tree.command(name='battle推理', description='相手のお題を推理する')
@app_commands.describe(答え='推理したお題')
async def battle_guess(i, 答え: str):
    match = battle_get_active(i.user.id)
    if not match:
        await i.response.send_message("⚔️ 現在参加中のBattleはありません。", ephemeral=True); return
    questioner = match[21] if len(match) > 21 and match[21] else match[1]
    if i.user.id != questioner:
        await i.response.send_message("❓ あなたは**回答者**です。推理できるのは質問者です。", ephemeral=True); return
    if len(答え.strip()) > 50 or not 答え.strip():
        await i.response.send_message("❌ 推理は1～50文字です。", ephemeral=True); return
    target = battle_topic_for(match,i.user.id)
    if 答え.strip() != target:
        await i.response.send_message("❌ **不正解！**\n質問を続けて、もう一度推理できます。", ephemeral=True); return

    loser = battle_other(match,i.user.id)
    delta = battle_change_rating(i.user.id,loser)
    item_type,item_name = give_battle_item(i.user.id)
    c = db(); c.execute("UPDATE battle_matches SET status='finished',winner=? WHERE match_id=?", (i.user.id,match[0])); c.commit(); c.close()
    await i.response.send_message(
        f"🎉 **正解！あなたの勝利です！**\n"
        f"🧠 お題：**{target}**（{BATTLE_TOPIC_CATEGORY[target]}）\n"
        f"🏆 **+{delta} Rating** / +100 Battle Point\n"
        f"🎁 **{item_type}：{item_name}** を獲得！", ephemeral=True)
    try:
        await (await bot.fetch_user(loser)).send(
            f"💥 Battle `{match[0]}` が終了しました。\n"
            f"相手が正解しました。お題は **{target}** でした。")
    except Exception:
        pass

@bot.tree.command(name='battle降参', description='現在のBattleを降参して終了する')
async def battle_surrender(i):
    match = battle_get_active(i.user.id)
    if not match:
        await i.response.send_message("⚔️ 現在参加中のBattleはありません。", ephemeral=True); return

    winner = battle_other(match, i.user.id)
    delta = battle_change_rating(winner, i.user.id)
    c = db()
    c.execute("UPDATE battle_matches SET status='finished',winner=? WHERE match_id=?", (winner, match[0]))
    c.commit(); c.close()

    await i.response.send_message(
        "🏳️ **降参しました。**\n"
        f"🏆 対戦相手の勝利です。相手に **+{delta} Rating / +100 Battle Point** が入ります。",
        ephemeral=True)
    try:
        await (await bot.fetch_user(winner)).send(
            f"🎉 **Battle `{match[0]}` 勝利！**\n"
            f"相手が降参しました。\n"
            f"🏆 **+{delta} Rating / +100 Battle Point**")
    except Exception:
        pass

@bot.tree.command(name='battleアイテム', description='Battleアイテムの所持数を見る')
async def battle_items(i):
    ensure_battle_profile(i.user.id)
    c=db(); rows=c.execute("SELECT item_name,item_type,quantity FROM battle_items WHERE user_id=? AND quantity>0 ORDER BY item_type,item_name",(i.user.id,)).fetchall(); c.close()
    if not rows:
        await i.response.send_message("🎒 Battleアイテムはまだありません。", ephemeral=True); return
    lines=["🎒 **Battleアイテム**"]
    for name,typ,qty in rows:
        lines.append(f"{'🔴' if typ=='攻撃' else '🔵'} **{name}** ×{qty}")
    await i.response.send_message("\n".join(lines)+"\n\n使う：`/battleアイテム使用`", ephemeral=True)

@bot.tree.command(name='battleアイテム使用', description='Battle中にアイテムを使う')
@app_commands.describe(アイテム='使用するBattleアイテム')
@app_commands.choices(アイテム=BATTLE_ITEM_CHOICES)
async def battle_item_use(i, アイテム: app_commands.Choice[str]):
    match=battle_get_active(i.user.id)
    if not match:
        await i.response.send_message("⚔️ Battle中のみアイテムを使えます。", ephemeral=True); return
    name=アイテム.value
    if not consume_battle_item(i.user.id,name):
        await i.response.send_message("🎒 そのアイテムを持っていません。", ephemeral=True); return
    other=battle_other(match,i.user.id)
    c=db()
    success=True; text=""
    if name == "追加質問カード":
        if match[5] != i.user.id:
            success=False; text="⏳ 自分の質問ターンに使ってください。"
        else:
            c.execute("UPDATE battle_matches SET extra_question_user=? WHERE match_id=?",(i.user.id,match[0]))
            text="🔥 **追加質問カード**を使いました。次の質問への回答後、もう一度質問できます。"
    elif name == "ヒントカード":
        if match[5] != i.user.id:
            success=False; text="⏳ 自分の質問ターンに使ってください。"
        elif match[15] == other:
            success=False; text="🛡️ 相手の情報隠蔽カードでヒントが防がれています。"
            c.execute("UPDATE battle_matches SET hidden_hint_user=NULL WHERE match_id=?",(match[0],))
        else:
            target=battle_topic_for(match,i.user.id)
            category=BATTLE_TOPIC_CATEGORY[target]
            text=f"💡 **ヒントカード**：相手のお題のカテゴリは **{category}** です。"
    elif name == "回答強制カード":
        if match[5] != i.user.id:
            success=False; text="⏳ 自分の質問ターンに使ってください。"
        else:
            c.execute("UPDATE battle_matches SET force_binary_user=? WHERE match_id=?",(other,match[0]))
            text="🎯 **回答強制カード**を使いました。相手の今回の回答は **YES / NO のみ** です。"
    elif name == "ガードカード":
        if match[5] == i.user.id or not match[11]:
            success=False; text="⏳ 相手から質問を受けている回答ターンに使ってください。"
        else:
            c.execute("UPDATE battle_matches SET forced_unknown_user=? WHERE match_id=?",(i.user.id,match[0]))
            text="🛡️ **ガードカード**を使いました。今回の回答は『わからない』になります。"
    elif name == "質問変更カード":
        if match[5] == i.user.id or not match[11]:
            success=False; text="⏳ 相手から質問を受けている回答ターンに使ってください。"
        else:
            text="🔄 **質問変更カード**を使いました。相手の質問は無効になり、もう一度質問し直します。"
            c.execute("UPDATE battle_matches SET turn_user=?,last_question=NULL,last_question_from=NULL,pending_change_user=NULL WHERE match_id=?",(other,match[0]))
    elif name == "情報隠蔽カード":
        c.execute("UPDATE battle_matches SET hidden_hint_user=? WHERE match_id=?",(i.user.id,match[0]))
        text="🕶️ **情報隠蔽カード**を使いました。相手がヒントカードを使ってもカテゴリが公開されません。"
    if not success:
        # 失敗時はアイテムを返す。
        c.execute("INSERT INTO battle_items(user_id,item_name,item_type,quantity) VALUES(?,?,?,1) ON CONFLICT(user_id,item_name) DO UPDATE SET quantity=quantity+1",(i.user.id,name,next(t for t,n in BATTLE_ITEM_POOL if n==name)))
    c.commit(); c.close()
    await i.response.send_message(text,ephemeral=True)
    if success:
        try:
            await (await bot.fetch_user(other)).send(f"⚔️ Battle `{match[0]}`\n{text}")
        except Exception:
            pass

@bot.tree.command(name='battleステータス', description='Battleの戦績を見る')
async def battle_status(i):
    ensure_battle_profile(i.user.id)
    c=db(); r=c.execute("SELECT rating,wins,losses,streak,best_streak,battle_points,total_games FROM battle_profiles WHERE user_id=?",(i.user.id,)).fetchone(); c.close()
    rating,wins,losses,streak,best,bp,games=r; rate=wins/games*100 if games else 0
    await i.response.send_message(f"⚔️ **Battle Status**\nランク：**{battle_rank(rating)}**\nRating：**{rating}**\n勝利：**{wins}**　敗北：**{losses}**\n勝率：**{rate:.1f}%**\n連勝：**{streak}**（最高 **{best}**）\nBattle Point：**{bp}**",ephemeral=True)

@bot.tree.command(name='battleランキング', description='全サーバー共通Battleランキング')
async def battle_ranking(i):
    c=db(); rows=c.execute("SELECT user_id,rating,wins,losses FROM battle_profiles ORDER BY rating DESC,wins DESC LIMIT 10").fetchall(); c.close()
    if not rows:
        await i.response.send_message("🏆 まだBattleランキングにデータがありません。",ephemeral=True); return
    lines=["🏆 **Battle Ranking（全サーバー共通）**"]
    for n,(uid,rating,wins,losses) in enumerate(rows,1):
        lines.append(f"{n}. <@{uid}> — **{battle_rank(rating)} / {rating}** | {wins}勝 {losses}敗")
    await i.response.send_message("\n".join(lines),ephemeral=True)

async def create_match(player1, player2, ranked=False):
    if battle_get_active(player1) or battle_get_active(player2): return None
    questioner, answerer = random.sample([player1, player2], 2)
    answerer_topic = random.choice(BATTLE_TOPICS)
    mid=f"B{random.randrange(0x1000000):06X}"
    c=db(); c.execute("""INSERT INTO battle_matches
        (match_id,player1,player2,player1_topic,player2_topic,questioner,answerer,answerer_topic,turn_user,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (mid,player1,player2,None,None,questioner,answerer,answerer_topic,questioner,"active",datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close()
    return mid

@bot.tree.command(name='battleランダム', description='全サーバー共通ランダムマッチ')
async def battle_random(i):
    ensure_battle_profile(i.user.id)
    if battle_get_active(i.user.id):
        await i.response.send_message("⚔️ すでにBattle中です。",ephemeral=True); return
    c=db(); existing=c.execute("SELECT user_id FROM battle_queue WHERE user_id=?",(i.user.id,)).fetchone()
    if existing:
        c.close(); await i.response.send_message("🔎 すでに待機中です。",ephemeral=True); return
    opponent=c.execute("SELECT user_id FROM battle_queue WHERE user_id<>? AND ranked=0 ORDER BY queued_at LIMIT 1",(i.user.id,)).fetchone()
    if opponent:
        oid=opponent[0]; c.execute("DELETE FROM battle_queue WHERE user_id=?",(oid,)); c.commit(); c.close()
        mid=await create_match(i.user.id,oid,False)
        await i.response.send_message(f"⚔️ **マッチング成功！**\n相手：<@{oid}>\n対戦ID：`{mid}`\n🌐 全サーバー共通です。\n\n役割はBotがランダムに決めます。詳細はDMを確認してください。",ephemeral=True)
        try:
            m=battle_get_active(i.user.id); qid=m[21] if len(m)>21 and m[21] else m[1]; aid=m[22] if len(m)>22 and m[22] else m[2]; topic=m[23] if len(m)>23 and m[23] else m[4]
            q=await bot.fetch_user(qid); a=await bot.fetch_user(aid)
            await q.send(f"❓ **あなたは質問者です！**\nBattle `{mid}`\n相手のお題を20問以内に当ててください。\n`/battle質問` で質問、`/battle推理` で推理できます。")
            await a.send(f"🧠 **あなたは回答者です！**\nBattle `{mid}`\n🔐 お題：**{topic}**\n質問されたら `/battle回答` で YES / NO / わからない と答えてください。\n🤔『わからない』は3回までです。")
        except Exception: pass
    else:
        c.execute("INSERT INTO battle_queue(user_id,server_id,queued_at,ranked) VALUES(?,?,?,0)",(i.user.id,i.guild.id if i.guild else 0,datetime.now(timezone.utc).isoformat())); c.commit(); c.close()
        await i.response.send_message("🔎 **ランダムマッチ待機中！**\n🌐 全サーバー共通の待機列です。",ephemeral=True)

@bot.tree.command(name='battleキャンセル', description='ランダムマッチ・ランクマッチの待機をキャンセル')
async def battle_cancel(i):
    c = db()
    r = c.execute("SELECT ranked FROM battle_queue WHERE user_id=?", (i.user.id,)).fetchone()
    if not r:
        c.close()
        await i.response.send_message("🔎 現在、マッチング待機中ではありません。", ephemeral=True)
        return
    mode = "ランクマッチ" if r[0] else "ランダムマッチ"
    c.execute("DELETE FROM battle_queue WHERE user_id=?", (i.user.id,))
    c.commit(); c.close()
    await i.response.send_message(f"🛑 **{mode}をキャンセルしました。**\n待機列から退出しました。", ephemeral=True)

@bot.tree.command(name='battleランクマッチ', description='全サーバー共通ランクマッチ')
async def battle_ranked(i):
    ensure_battle_profile(i.user.id)
    if battle_get_active(i.user.id):
        await i.response.send_message("⚔️ すでにBattle中です。",ephemeral=True); return
    c=db(); me=c.execute("SELECT rating FROM battle_profiles WHERE user_id=?",(i.user.id,)).fetchone(); existing=c.execute("SELECT user_id FROM battle_queue WHERE user_id=?",(i.user.id,)).fetchone()
    if existing:
        c.close(); await i.response.send_message("🔎 すでにマッチング待機中です。",ephemeral=True); return
    rating=me[0] if me else 1000
    opponent=c.execute("SELECT user_id,rating FROM battle_queue q JOIN battle_profiles p ON p.user_id=q.user_id WHERE q.user_id<>? AND q.ranked=1 AND ABS(p.rating-?)<=250 ORDER BY ABS(p.rating-?) LIMIT 1",(i.user.id,rating,rating)).fetchone()
    if opponent:
        oid=opponent[0]; c.execute("DELETE FROM battle_queue WHERE user_id=?",(oid,)); c.commit(); c.close(); mid=await create_match(i.user.id,oid,True)
        await i.response.send_message(f"🏆 **ランクマッチ成立！**\n相手：<@{oid}>\n対戦ID：`{mid}`\n🌐 全サーバー共通です。\n\n役割はBotがランダムに決めます。詳細はDMを確認してください。",ephemeral=True)
        try:
            m=battle_get_active(i.user.id); qid=m[21] if len(m)>21 and m[21] else m[1]; aid=m[22] if len(m)>22 and m[22] else m[2]; topic=m[23] if len(m)>23 and m[23] else m[4]
            q=await bot.fetch_user(qid); a=await bot.fetch_user(aid)
            await q.send(f"❓ **あなたは質問者です！**\nBattle `{mid}`\n相手のお題を20問以内に当ててください。\n`/battle質問` で質問、`/battle推理` で推理できます。")
            await a.send(f"🧠 **あなたは回答者です！**\nBattle `{mid}`\n🔐 お題：**{topic}**\n質問されたら `/battle回答` で YES / NO / わからない と答えてください。\n🤔『わからない』は3回までです。")
        except Exception: pass
    else:
        c.execute("INSERT INTO battle_queue(user_id,server_id,queued_at,ranked) VALUES(?,?,?,1)",(i.user.id,i.guild.id if i.guild else 0,datetime.now(timezone.utc).isoformat())); c.commit(); c.close()
        await i.response.send_message(f"🏆 **ランクマッチ待機中！**\n現在：**{battle_rank(rating)} / {rating}**\n±250 Rating以内の相手を探します。",ephemeral=True)

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
