from dataclasses import dataclass


@dataclass(frozen=True)
class Tag:
    id: str
    label: str
    description: str
    family: str
    branch: str
    kind: str = "style"
    aliases: tuple[str, ...] = ()
    reference: str = ""
    name: str = ""


def group(family, branch, rows, kind="style"):
    for line in rows.strip().splitlines():
        key, name, sound, *aliases = line.strip().split(" | ")
        yield Tag(key, name, sound, family, branch, kind, tuple(aliases))


def scene_group(family, rows):
    for line in rows.strip().splitlines():
        key, label, name, sound, reference, *aliases = line.strip().split(" | ")
        yield Tag("cue-" + key, label, sound, family, family, "scene", tuple(aliases), reference, name)


STYLES = (
    *group("Electronic", "House", """
deep-house | Deep House | deep house with warm jazzy chords, a rounded bassline and a steady kick
acid-house | Acid House | acid house with a squelching resonant TB-303 line and drum-machine pulse
progressive-house | Progressive House | progressive house, layered synth motifs and a long evolving four-on-the-floor build
    """),
    *group("Electronic", "Techno", """
detroit-techno | Detroit Techno | Detroit techno with mechanical percussion, soulful futuristic synths and motoric repetition
dub-techno | Dub Techno | dub techno with submerged chords, spacious delay and a restrained four-on-the-floor kick
minimal-techno | Minimal Techno | minimal techno with sparse repetitive percussion and subtle changes in a lean club groove
    """),
    *group("Electronic", "Trance / Hard Dance", """
uplifting-trance | Uplifting Trance | trance with bright sustained synth arpeggios, long breakdown and melodic four-on-the-floor climax
psytrance | Psytrance | psychedelic trance, rapid rolling bass beneath a steady kick and shifting spiralling synths
goa-trance | Goa Trance | melodic psychedelic trance with layered winding acid-like synth lines and persistent fast dance pulse
hardstyle | Hardstyle | hard dance with distorted pitched kicks, emphatic build-ups and large melodic leads
    """),
    *group("Electronic", "Breaks / Drum & Bass", """
uk-garage | UK Garage | swung two-step garage, skipped kick pattern, clipped vocal fragments and supple sub bass | UKG
jungle | Jungle | jungle with rapid chopped breakbeats, deep bass, dub delays and ragga accents
liquid-dnb | Liquid Drum & Bass | fast drum and bass with flowing breakbeats, smooth chords and soulful melodic pads | Liquid Funk
neurofunk | Neurofunk | drum and bass with fast precise beats and modulated, dark, mechanical bass riffs
breakcore | Breakcore | breakcore, frantic chopped breaks, abrupt edits and extreme rhythmic fragmentation
    """),
    *group("Electronic", "Bass / Club", """
dubstep | Dubstep | half-time dubstep with a sparse syncopated snare, deep sub bass and dark space
footwork | Footwork | footwork with rapid syncopated kicks, repeating cut-up chants and sharp polyrhythmic percussion
grime-instrumental | Instrumental Grime | grime instrumental, terse square-wave leads and angular sparse syncopated drums
amapiano | Amapiano | South African club music with syncopated log drum bass, shakers and warm airy keyboard chords
gqom | Gqom | spare South African club beat with repetitive dark percussion, low kicks and asymmetric accent patterns
    """),
    *group("Electronic", "Ambient / Experimental", """
ambient | Ambient | ambient electronic music with slowly changing spacious pads and few rhythmic accents
drone | Drone | sustained tones with slowly shifting overtones and minimal rhythmic or harmonic movement
idm | IDM | intricate programmed beats, off-grid syncopation and abstract melodic synth patterns
glitch | Glitch | electronic composition built around clicks, interruptions, stutters and digital artifacts
industrial | Industrial | industrial electronics with abrasive noise, mechanical repetitions and harsh metallic percussion
ebm | EBM | electronic body music with rigid dance pulse, sequenced bass and stern rhythmic vocals
    """),
    *group("Electronic", "Retro / Digital media", """
synthwave | Synthwave | synthwave with pulsing analog-style arpeggios, electronic drums and cinematic retro leads
vaporwave | Vaporwave | slowed and cut-up lounge or pop samples, warped pitch and soft reverberant transitions
chiptune | Chiptune | chip music with square-wave melody, simple pulse bass and noise-channel percussion
    """),
    *group("Rock", "Alternative guitars", """
garage-rock | Garage Rock | raw compact rock with fuzzy simple guitar riffs and rough live-band drums
post-punk | Post-Punk | post-punk with angular guitar, prominent melodic bass and clipped insistent drums
math-rock | Math Rock | clean interlocking guitar figures in shifting odd meters and abrupt rhythmic changes
indie-rock | Indie Rock | melodic independent guitar rock with live drums and direct band arrangement
post-rock | Post-Rock | largely instrumental rock, slowly layered motifs and expansive crescendos across long sections
shoegaze | Shoegaze | thick layered effected guitars, sustained fuzz and soft vocals partly buried in the guitar wash
    """),
    *group("Rock", "Art / Psychedelia", """
psychedelic-rock | Psychedelic Rock | rock band with swirling effects, modal riffs and extended psychedelic passages
progressive-rock | Progressive Rock | long-form rock with metric changes, contrasting sections and keyboards or virtuosic solos
    """),
    *group("Rock", "Punk / Hardcore", """
punk-rock | Punk Rock | fast short songs, raw power chords, direct shouted vocals and stripped-down drums
hardcore-punk | Hardcore Punk | frantic punk, compressed distorted riffs, forceful shouted vocals and abrupt fast breaks
emo | Emo | intimate strained melodic vocals, ringing guitars and emotionally charged dynamic changes
    """),
    *group("Rock", "Heavy metal", """
heavy-metal | Heavy Metal | classic amplified metal, galloping riffs, clear powerful vocals and guitar solos
thrash-metal | Thrash Metal | fast tight palm-muted metal riffs with aggressive drums and rasped vocals
death-metal | Death Metal | low guttural vocals, heavily distorted chromatic riffs and tightly accented fast drums
black-metal | Black Metal | shrieked vocals, rapid thin tremolo guitar and blast beats
doom-metal | Doom Metal | slow heavy sustained low riffs, spacious drums and dark long chords
power-metal | Power Metal | fast melodic metal, soaring clean vocals, bright harmonized guitars and double kick
metalcore | Metalcore | alternating screamed and melodic vocals, chugging syncopated guitars and half-time breakdowns
    """),
    *group("Rock", "Atmospheric / hybrid metal", """
post-black-metal | Post-Black Metal | black metal tremolo, blast beats and harsh vocals alternating with wide dynamic post-rock crescendos
blackgaze | Blackgaze | sustained dreamy shoegaze guitar layers combined with black metal tremolo, harsh screams or blast beats
sludge-metal | Sludge Metal | slow thick abrasive metal riffs, rough shouted vocals and murky heavy groove
    """),
    *group("Folk, World, & Country", "Country / Folk", """
old-time | Appalachian Old-Time | Appalachian fiddle and clawhammer banjo playing repetitive dance tunes with acoustic accompaniment
bluegrass | Bluegrass | rapid acoustic banjo, fiddle and mandolin breaks with tight vocal harmony
honky-tonk | Honky Tonk | country dance hall beat with pedal steel, twangy guitar and an upfront singing voice
outlaw-country | Outlaw Country | rugged country baritone, twangy electric guitars and a loose country-rock backing
americana | Americana | roots singer-songwriter with acoustic guitar, folk storytelling and country or blues inflections
    """),
    *group("Folk, World, & Country", "East Asian traditions", """
guqin | 古琴独奏 | spare Chinese guqin zither with plucked strings, sliding glissandi, harmonics and open space | Guqin
jiangnan-sizhu | 江南丝竹 | Jiangnan silk and bamboo ensemble with interwoven Chinese flute, bowed strings and plucked instruments
minyo | Min’yō | Japanese traditional folk singing, ornamented call and response with shamisen or folk percussion | Minyo
pansori | Pansori | Korean narrative singing with dramatic declamation, flexible phrasing and a single barrel drum
khoomei | Khöömei | Mongolian or Tuvan overtone singing with focused upper harmonics over a low vocal drone | Khoomei | 呼麦
    """),
    *group("Folk, World, & Country", "Southeast Asian / Pacific traditions", """
gamelan | Gamelan | Indonesian ensemble of tuned metallophones and gongs, interlocking patterns and cyclical accents
kroncong | Kroncong | Indonesian kroncong with small plucked string instruments, flute and softly syncopated singing | Keroncong
luk-thung | Luk Thung | Thai country pop, ornamented lead singing and rural dance-song accompaniment
mor-lam | Mor Lam | Northeastern Thai or Lao-style expressive singing with continuous khaen reed harmonies and nimble rhythmic patterns
dangdut | Dangdut | Indonesian popular dance song with distinctive hand drum patterns, ornamented voice and flute or electric backing
ca-tru | Ca Trù | Vietnamese chamber singing with plucked lute, wooden timekeeping sticks and flexible ornamented vocal phrases
pin-peat | Pin Peat | Cambodian ensemble with layered tuned gongs and xylophones, piercing reeds and cyclic percussion
slack-key | Slack-key Guitar | Hawaiian open-tuned acoustic guitar with alternating bass and gently picked melodic lines | Ki ho‘alu
    """),
    *group("Folk, World, & Country", "South Asian song", """
qawwali | Qawwali | South Asian ensemble singing with harmonium, handclaps, answering chorus and rising rhythmic intensity
ghazal | Ghazal | ornamented South Asian sung verse with spacious phrasing and light harmonium or tabla accompaniment
bhangra | Bhangra | Punjabi dance groove with emphatic dhol rhythm, energetic sung calls and repetitive melodies
bhajan | Bhajan | melodic South Asian devotional song with repeated response, hand percussion and harmonium or drone
baul | Baul | Bengali Baul singing with an unadorned leading voice, plucked one-string drone and small hand percussion
    """),
    *group("Folk, World, & Country", "West Asian / North African traditions", """
gnawa | Gnawa | Moroccan Gnawa ensemble with low guembri ostinato, metallic qraqeb and call-and-response singing
rai | Raï | Algerian Raï singing with melismatic lead, lilting percussion and electric accompaniment | Rai
taqsim | Taqsim | unmetered modal instrumental improvisation with ornamented oud, qanun or ney phrasing
dutar-tradition | Dutar song | Central Asian long-necked two-string lute picking and ornamented solo song or instrumental melody
dabke | Dabke | Levantine dance music with strongly marked stepping accents, sharp reed melody and driving drums
    """),
    *group("Folk, World, & Country", "Sub-Saharan traditions / popular music", """
mbira | Mbira music | interlocking thumb piano cycles, buzzing overtones, shakers and layered singing
maskandi | Maskandi | South African Zulu guitar music with iterative picking, strong vocal narrative and driving syncopation
mbalax | Mbalax | Senegalese dance music with layered sabar rhythms, dense percussion and strong vocal lines
highlife | Highlife | West African dance band with interlocking high guitar riffs, lilting pulse and bright brass
taarab | Taarab | East African coastal singing, ornamented strings, oud-like timbres and swaying percussion
afrobeat | Afrobeat | long West African funk grooves with interlocking drums, repeating guitar parts and riffing horn sections
afrobeats | Afrobeats | contemporary West African pop with syncopated electronic percussion, melodic vocals and a buoyant bassline
soukous | Soukous | bright Congolese dance band, agile interlocking electric guitar patterns and rolling dance pulse
ethio-jazz | Ethio-Jazz | Ethiopian melodic modes and expressive horn lines set against syncopated jazz rhythm
    """),
    *group("Folk, World, & Country", "European / Caucasian traditions", """
irish-trad | Irish Trad | Irish fiddle, flute and pipes playing quick reels or jigs with ornamented unison melody
fado | Fado | Portuguese dramatic solo song with articulated Portuguese guitar and spare acoustic accompaniment
rebetiko | Rebetiko | Greek urban song with bouzouki, baglamas, modal melody and close ensemble interplay
georgian-polyphony | Georgian Polyphonic Singing | Georgian ensemble singing with independent vocal lines, drones or closely interlocking harmonies
flamenco | Flamenco | flamenco guitar, accented palmas and expressive melismatic singing in a compás rhythm
    """),
    *group("Folk, World, & Country", "American / Caribbean traditions", """
zydeco | Zydeco | accordion-led Louisiana dance sound, rubboard percussion and a driving syncopated beat
andean-huayno | Andean Huayno | Andean huayno with lilting dance rhythm, charango or harp and high sung or pipe melodies
bomba | Bomba | Puerto Rican call-and-response voice and hand percussion with conversational lead barrel drum
garifuna | Garifuna music | Garifuna drum ensemble, syncopated hand drum patterns and communal sung response
    """),
    *group("Latin", "Caribbean dance", """
son-cubano | Son Cubano | Cuban son with tres, clave, bass tumbao and call-and-response chorus
salsa-dura | Salsa Dura | brass-forward salsa with driving clave, piano montuno and busy hand percussion
timba | Timba | Cuban dance band with dense syncopation, sharp rhythmic breaks, keyboards and powerful brass
bachata | Bachata | Bachata with accented plucked lead guitar, rolling bongos and swaying four-beat rhythm
merengue | Merengue | rapid Dominican dance rhythm with güira and tambora driving a steady two-step pulse
reggaeton | Reggaeton | repeated dembow rhythm with punchy bass and rhythmic Spanish-language vocal phrasing
    """),
    *group("Latin", "Brazilian popular / dance", """
samba | Samba | Brazilian samba with layered drums, surdo pulse and rhythmic small string accompaniment
bossa-nova | Bossa Nova | soft syncopated Brazilian guitar chords, quiet singing and understated jazz harmony
forro | Forró | Brazilian dance groove with accordion, triangle, zabumba and swinging bass accents
funk-carioca | Funk Carioca | Brazilian baile funk with syncopated electronic tamborzão percussion and rhythmic vocal chants | Baile Funk
mpb | MPB | Brazilian popular song with expressive Portuguese singing, textured acoustic rhythm and rich harmony
    """),
    *group("Latin", "Continental song / dance", """
cumbia | Cumbia | cumbia with cyclical swaying percussion, bass pattern, accordion or guiro-like texture
tango | Tango | articulated tango pulse with bandoneon, strings, dramatic stops and expressive melody
mariachi | Mariachi | trumpet and violin ensemble, fast strummed guitars and strong resonant singing
norteno | Norteño | northern Mexican dance and song with accordion, bajo sexto and polka-like rhythm
corrido | Corrido | narrative Mexican ballad with clearly articulated story verses and regional string or accordion backing
bolero | Bolero | slow Latin romantic song with guitar or small orchestra, gentle rhythm and lyrical singing
    """),
    *group("Hip Hop", "Rap / beat traditions", """
boom-bap | Boom Bap | sampled hip hop with prominent kick-and-snare pattern and short repeating sample loop
g-funk | G-Funk | West Coast hip hop with smooth funk bass, high gliding synthesizer leads and a relaxed groove
jazz-rap | Jazz Rap | rapped vocals over jazz chord samples, soft upright bass and sampled drums
instrumental-hip-hop | Instrumental Hip Hop | instrumental sampled hip hop beats with looped rhythm, instrumental motifs and no lead rap
trap | Trap | hip hop with long sub bass, sharp rapid hi-hat rolls and sparse electronic backing
drill | Drill | rap over sliding sub bass and shifting angular kick-and-snare syncopation
cloud-rap | Cloud Rap | floating rap vocals and misty reverberant synth textures over a restrained beat
    """),
    *group("Hip Hop", "Phonk", """
memphis-phonk | Memphis Phonk | dark lo-fi phonk with chopped Memphis rap samples, dusty percussion and a hazy melodic loop
drift-phonk | Drift Phonk | fast distorted phonk with repeating cowbell motifs, clipped rap cuts and heavy sub bass
phonk-house | Phonk House | phonk with a steady four-on-the-floor kick, house structure and chopped Memphis rap
brazilian-phonk | Brazilian Phonk | highly distorted Brazilian phonk production with clipped bass, syncopated baile funk percussion and chopped vocal calls
    """),
    *group("Jazz", "Early / Swing", """
new-orleans-jazz | New Orleans Jazz | early jazz with collective horn interplay, clarinet or trumpet, and a parade-like swing groove
swing | Swing | jazz big band with swung pulse, antiphonal brass and reed sections
    """),
    *group("Jazz", "Modern acoustic", """
bebop | Bebop | small-group jazz with agile improvised horn lines, walking bass and quick chord changes
cool-jazz | Cool Jazz | restrained jazz phrasing, light drums, soft horn tone and spacious arrangements
hard-bop | Hard Bop | driving small-group jazz with blues-inflected hard horn lines and gospel accents
modal-jazz | Modal Jazz | jazz improvisation over long modal sections, repeating bass figures and open harmony
spiritual-jazz | Spiritual Jazz | expansive modal jazz with devotional atmosphere, layered percussion and soaring improvisation
free-jazz | Free Jazz | collective jazz improvisation, irregular rhythm, abrasive timbres and loose harmonic form
    """),
    *group("Jazz", "Fusion / Latin", """
jazz-fusion | Jazz Fusion | virtuoso jazz improvisation with electric instruments, complex changes and rock or funk rhythm
latin-jazz | Latin Jazz | jazz harmonic improvisation over clave, congas and Latin dance rhythms
jazz-manouche | Jazz Manouche | acoustic string swing with fast lead guitar and percussive la pompe accompaniment | Gypsy Jazz
    """),
    *group("Pop", "Mainstream / vocal", """
vocal-pop | Vocal Pop | prominent melodic lead vocal, steady accessible chords and a chorus-centered studio arrangement
power-pop | Power Pop | short bright guitar songs with crisp drums, layered harmonies and strong chorus hooks
dance-pop | Dance-Pop | polished pop vocal, repetitive catchy chorus and steady electronic dance beat
synthpop | Synthpop | melodic pop song form built on drum machines and bright layered synthesizers | Synth-Pop
    """),
    *group("Pop", "Indie / digital", """
dream-pop | Dream Pop | gentle melodic vocals, luminous pads and hazy reverberant guitars with a soft pop pulse
indie-pop | Indie Pop | intimate pop hooks with light guitar, understated arrangements and small-scale production
city-pop | City Pop | polished Japanese-style urban pop with fusion chords, nimble bass and bright band or synthesizer arrangements
hyperpop | Hyperpop | exaggerated digitally processed vocals, extreme bright hooks and sharply edited electronic pop
    """),
    *group("Funk / Soul", "Funk / disco", """
deep-funk | Deep Funk | tight raw syncopated funk band with repeated guitar and bass riffs and emphatic organic drums
p-funk | P-Funk | elastic psychedelic funk with thick bass, talkbox-like leads and layered group vocals | Parliament-Funkadelic style
jazz-funk | Jazz-Funk | electric piano and jazz chords over a tight funk rhythm section with instrumental improvisation
disco | Disco | steady four-on-the-floor dance beat, syncopated bass and glittering strings or guitar
boogie | Boogie | post-disco electronic funk with drum machine, squelchy synth bass and soulful vocals
    """),
    *group("Funk / Soul", "Soul / R&B", """
motown-style | Motown-style Soul | energetic vintage soul with tambourine backbeat, bass-driven grooves and stacked vocal harmonies
southern-soul | Southern Soul | warm gritty gospel-inflected singing over slow bluesy organ, brass and rhythm section
neo-soul | Neo-Soul | conversational soul singing, extended jazz chords and laid-back groove with warm electric piano
contemporary-rnb | Contemporary R&B | rhythmic melismatic vocal, layered harmony and polished bass-heavy modern R&B production
new-jack-swing | New Jack Swing | clipped swinging drum-machine patterns beneath polished layered R&B singing
    """),
    *group("Classical", "European art music periods", """
early-polyphony | Early Vocal Polyphony | unaccompanied interwoven moving vocal lines and clear counterpoint
baroque-chamber | Baroque Chamber Music | chamber strings or winds with continuo, ornamental counterpoint and clear patterned pulse
classical-chamber | Classical-era Chamber Music | balanced phrases and light articulated motivic interplay among a small acoustic ensemble
romantic-orchestral | Romantic Orchestral | large acoustic orchestra with rich chromatic harmony, long swelling melodies and broad dynamics
musical-impressionism | Musical Impressionism | shifting coloristic harmony, delicate instrumentation and flowing ambiguous tonality
    """),
    *group("Classical", "Modern / electroacoustic", """
serialism | Serialism | modernist instrumental music with angular non-tonal lines and pointillistic texture
musical-minimalism | Musical Minimalism | repeated tonal cells changing gradually, steady pulse and incremental layering
electroacoustic | Electroacoustic | art music assembled from transformed recorded sounds and abstract spatial electronic textures
    """),
    *group("Classical", "Vocal / regional art traditions", """
opera | Opera | projected operatic solo singing with orchestral accompaniment and theatrical dynamics
art-song | Art Song | solo classical voice with expressive piano accompaniment and lyric-centered phrasing
hindustani | Hindustani Classical | North Indian raga unfolding over a drone, ornamented melodic elaboration and tabla when rhythmic sections enter
carnatic | Carnatic Classical | South Indian classical melodic ornaments, intricate tala, drone and mridangam accompaniment
dastgah | Persian Dastgāh | Persian art music with fluid vocal or instrumental modal phrasing, tar or santur and ornamented improvisation
gagaku | Gagaku | Japanese court music with slow wind and reed organ sonorities, spacious percussion and formal phrase pacing
    """),
    *group("Blues", "Acoustic traditions", """
delta-blues | Delta Blues | raw solo blues vocal with sliding acoustic guitar and strong repeated rhythmic figures
piedmont-blues | Piedmont Blues | acoustic blues with alternating thumb bass and ragtime-influenced fingerpicked upper melody
country-blues | Country Blues | acoustic rural blues song with sparse guitar accompaniment and flexible singing
    """),
    *group("Blues", "Electric traditions", """
chicago-blues | Chicago Blues | amplified blues band, harmonica or electric guitar, shuffling drums and forceful singing
texas-blues | Texas Blues | electric blues with expressive lead-guitar bends, shuffle groove and open solo phrasing
jump-blues | Jump Blues | upbeat riffing horns and boogie rhythm behind blues vocals
    """),
    *group("Reggae", "Jamaican band traditions", """
ska | Ska | bright horns and quick offbeat guitar chords over walking bass
rocksteady | Rocksteady | relaxed Jamaican offbeat rhythm with prominent bass and close vocal harmonies
roots-reggae | Roots Reggae | deep bass, one-drop drums, offbeat guitar and reflective roots singing
lovers-rock | Lovers Rock | soft melodic reggae with gentle romantic soul vocals and warm offbeat rhythm
    """),
    *group("Reggae", "Dub / digital", """
dub | Dub | sparse remix of reggae bass and drum groove with long echoes, dropouts and reverberant fragments
digital-dancehall | Digital Dancehall | digital Jamaican riddim with sharply syncopated drum-machine hits, repetitive bass and rhythmic vocals
    """),
    *group("Brass & Military", "Brass ensembles", """
british-brass-band | British Brass Band | large tightly voiced cornet, tenor horn and low brass ensemble with formal phrasing
new-orleans-brass | New Orleans Brass Band | lively street brass ensemble with sousaphone bass, second-line drums and improvised horn riffs
military-march | Military March | regular marching pulse, military snare patterns and formal brass or wind-band fanfare
    """),
    *group("Stage & Screen", "Soundtrack idioms", """
orchestral-score | 管弦配乐式 | wide orchestral themes with cinematic swells, tension cues and dramatic texture changes
suspense-score | 悬疑电子配乐式 | restrained suspense underscore with quiet pulsing bass, tension drones and sparse electronic accents
game-loop | 游戏循环配乐式 | loopable arranged cue with repeating motifs and smooth returns to the opening texture
    """),
    *group("Stage & Screen", "Stage performance", """
musical-theatre | Musical Theatre style | story-driven ensemble vocals, spoken or dramatic singing and theatre orchestra accompaniment
    """),
    *group("Children's", "Singing and play", """
sing-along | 童谣齐唱 | clear simple repeating melody and group voices with light rhythmic accompaniment
lullaby | Lullaby | quiet gentle rocking melody, soft voice or instruments and little percussion
movement-song | 律动游戏歌 | repeated movement-friendly chants, steady accessible tempo and clapping or simple percussion
    """),
    *group("Non-Music", "Speech and sound", """
spoken-word | Spoken Word | clearly articulated spoken voice or recitation with minimal musical accompaniment
field-recording | Field Recording | documentary environmental sounds, natural space or street ambience with no regular musical pulse
sound-art | Sound Art | arranged sound textures, environmental recordings and abstract non-song-form changes
    """),
)


SCENES = (
    *scene_group("年代音色", """
early-mono | 窄带单声道音色 | Band-limited mono texture | band-limited mono music with a narrow centered soundstage, softened high frequencies and clearly audible low-fidelity recording texture | clean recording :: a clean full-bandwidth music recording
vintage-studio | 复古乐队录音室制作 | Vintage analog studio production | vintage soul or psychedelic studio sound with saturated tape, spring reverb, Hammond organ and a dry live rhythm section | modern studio band :: a studio band playing guitars, keyboards, bass and drums
eighties-synth | 80 年代合成器制作 | 1980s synth-pop production | 1980s synth-pop production with gated snare reverb, FM electric keys, analog sequencer bass and glossy synthesizer leads | modern electronic pop :: electronic pop music with keyboards, a bassline and drums
nineties-sampling | 90 年代采样制作 | 1990s boom-bap sampling | dusty 1990s boom-bap sampling with chopped vinyl breaks, audible record scratches, short jazz loops and swinging MPC drums | modern hip-hop :: hip-hop music with sampled instruments and programmed drums
y2k | Y2K | Y2K revival internet music | nostalgic early-internet pop or melodic rap with glossy retro-digital synth bells, twinkling rompler keys, chopped R&B samples and hazy pitch-processed vocals over syncopated drums | contemporary pop and melodic rap :: contemporary pop or R&B with sung vocals, keyboard chords, a bassline and electronic drums | Y2K 流行／R&B 制作
swag-2000s | 2000sswag | 2000s underground swag rap | nostalgic underground melodic rap with an audible rapped lead, chopped soul samples, glossy digital synth phrases and loose swaggering hip-hop drums | contemporary melodic hip-hop :: melodic hip-hop with vocals, synthesizers and a drum beat | 2000sswag 地下旋律说唱
seventies-disco | 70 年代迪斯科制作 | 1970s disco production | vintage disco production with wah-wah rhythm guitar, sweeping string sections, syncopated octave bass and handclaps around a live four-on-the-floor beat | contemporary dance :: dance music with bass, strings, guitars and a steady drum beat
nineties-rave | 90 年代锐舞音色 | 1990s rave production | early rave sound with sampled orchestra-hit stabs, hoover synths, chopped breakbeats, pitched vocal shouts and harsh digital sampler texture | contemporary electronic dance :: fast electronic dance music with synthesizers and drums
    """),
    *scene_group("网络制作", """
vaporwave | Vaporwave 声音线索 | Vaporwave | slowed and pitch-lowered smooth-jazz or commercial-pop samples with woozy loops, artificial reverb and an obviously warped nostalgic texture | smooth instrumental :: smooth instrumental music with synthesizers, saxophone and a relaxed beat
future-funk | Future Funk 声音线索 | Future funk sample editing | tightly chopped disco or Japanese city-pop samples repeatedly gated to a pumping house kick with bright filter sweeps | disco and house :: upbeat disco or house music with vocals and a dance beat
mallsoft | Mallsoft 空间音色 | Mallsoft | muffled instrumental easy-listening music heard through a distant shopping-mall speaker with oversized empty-room reverberation | easy-listening background :: instrumental background music with a soft melody and reverb
digicore | Digicore 数字制作 | Digicore | intimate pitch-corrected rap singing over brittle clipped drums, glittering synthetic arpeggios and abrupt glitchy digital edits | melodic electronic rap :: melodic rap with synthesizers, sung vocals and electronic drums
scenecore | Scenecore 失真制作 | Scenecore | heavily pitch-shifted autotuned vocals, distorted buzzy synth leads, clipped club drums and harsh compressed digital effects | electronic pop :: fast electronic pop music with processed vocals and synthesizers
anime-break-edit | 动画采样碎拍剪辑 | Anime-sample breakbeat edits | clearly chopped anime-like spoken or sung voice samples abruptly interrupted by rapidly rearranged jungle breaks and glitch cuts | fast breakbeat :: fast breakbeat music with vocals and electronic sounds
phonk-edit | Phonk 漂移剪辑音色 | Drift phonk edits | clipped cowbell riffs and heavily distorted 808 bass under chopped low Memphis-style rap shouts with aggressive abrupt edit transitions | bass-heavy hip-hop :: bass-heavy hip-hop with rap vocals and electronic percussion
tracker-scene | Tracker／Demoscene 音色 | Tracker and demoscene music | old tracker-module sound with tiny looping instrument samples, arpeggiated chip leads, rigid channel-limited drums and crunchy low-bit playback | sequenced electronic :: instrumental electronic music with arpeggios and programmed drums
speed-edit | 变速剪辑音色 | Sped-up pitch-shifted edits | conspicuously accelerated and high-pitched recorded singing with unnaturally fast syllables, chipmunk-like formants and shortened drum transients | fast pop :: fast pop music with high-register vocals and a drum beat
synthetic-singer | 合成歌声音色 | Vocaloid-style synthetic singing | an artificial singing voice with sharply synthesized vowel changes, robotic consonants, perfectly stepped pitch and synthetic breaths | pitch-corrected human singing :: a human lead singer with pitch correction and electronic accompaniment
short-edit | 短段拼接线索 | Hard-cut audio edits | repeated very short hook snippets interrupted by reverse swells, tape-stop effects, hard jump cuts and abrupt changes of audio texture | conventionally arranged :: music with repeated melodic phrases and ordinary transitions
    """),
    *scene_group("录音制作", """
tape-texture | 磁带质感 | Cassette tape texture | clearly audible cassette hiss, fluttering pitch, softened treble and magnetic-tape saturation around the music | warm clean recording :: a warm music recording with soft high frequencies
lofi-collage | Lo-Fi 采样拼贴 | Lo-fi sample collage | vinyl crackle and dusty chopped samples with disjointed loop edges, deliberately degraded fidelity and short collage-like edits | sampled instrumental :: music with repeating sampled instruments and a relaxed rhythm
intimate-room | 近距小空间录音感 | Intimate home recording | a very close unpolished acoustic performance with audible breathing, finger noise, short room reflections and quiet domestic background sounds | clean acoustic studio :: a clean studio recording of acoustic instruments and a singer
large-hall | 大厅演奏空间感 | Concert hall acoustics | distant acoustic musicians surrounded by a long naturally decaying concert-hall reverberation and a wide ensemble soundstage | reverberant instrumental :: orchestral or instrumental music with added reverb
live-audience | 现场观众声线索 | Live audience sounds | music accompanied by clearly audible crowd cheers, applause, audience singing and calls from the stage | studio performance :: a clean studio music performance with instruments and vocals
dense-digital | 高密度数字制作 | Clipped dense digital production | extreme audible sidechain pumping, brickwall-clipped transients, sharply spliced synth layers and deliberately crushed digital distortion | loud electronic :: a loud electronic recording with synthesizers and drums
wall-of-sound | 噪音墙叠层质感 | Shoegaze wall of sound | many layers of fuzzy reverberant guitars merging into a nearly continuous noisy wall with buried vocals and slow-moving harmonies | distorted guitar rock :: rock music with distorted electric guitars and sung vocals
field-recording | 环境实录融合 | Musical field recordings | audible rain, birds, street voices or other natural environmental recordings integrated as a prominent continuous musical layer | atmospheric instrumental :: atmospheric instrumental music with synthetic background textures
vinyl-scratch | 唱盘刮碟制作 | Turntable scratching | rhythmic back-and-forth vinyl scratching, turntable rewinds, crossfader cuts and repeated tiny sampled syllables | sampled hip-hop :: sampled hip-hop music with drums and a vocal
acoustic-one-take | 原声同期演奏感 | Acoustic live-room recording | audible shared-room acoustic performance with count-ins, chair or finger noises, natural instrumental bleed and small live timing variations | acoustic studio :: polished studio music played on acoustic instruments
    """),
    *scene_group("舞池与表演", """
sound-system | Sound System 制作语汇 | Dub sound-system mixing | dub sound-system mixing with exceptionally deep sub-bass, sparse offbeat skanks, long ping-pong tape echoes and sudden reverb dropouts | bass-heavy :: bass-heavy music with a steady rhythm and reverberant instruments
club-build | 舞池渐进编排 | DJ-friendly club arrangement | extended DJ-friendly club arrangement with an exposed kick intro, gradual filter builds, a tension break and a clear beat drop | electronic dance :: electronic dance music with a regular beat and repeating synthesizer phrases
street-dance | 街舞断拍线索 | Breakdance drum loops | exposed funk drum breaks repeatedly looped for dance, turntable cuts and sharply syncopated breakdance accents | syncopated funk :: groove-based music with a bassline and syncopated drums
festival-drop | 音乐节式落差编排 | Festival EDM drops | a huge electronic build with snare-roll acceleration and a rising pitch sweep followed by a sudden loud festival-style bass drop | electronic dance :: energetic electronic dance music with synthesizers and drums
warehouse-rave | 仓库锐舞空间感 | Industrial warehouse rave | pounding industrial kick loops, raw distorted percussion and long cavernous warehouse-like echoes around repetitive machine rhythms | electronic techno :: repetitive techno music with electronic percussion
ballroom-runway | Ballroom／Runway 律动 | Ballroom vogue runway music | a stripped runway house beat with sharply chopped diva commands, repeated crash accents and a syncopated dramatic vogue-like rhythmic pattern | house :: house music with sampled voices and a steady dance beat
latin-party | 拉丁舞会打击编制 | Afro-Latin dance ensemble | a clear Afro-Latin clave pattern with interlocking congas, timbales, cowbell, piano montuno and a dance-band bass tumbao | rhythmic band :: rhythmic band music with percussion, piano and bass
    """),
    *scene_group("影视与游戏配乐", """
chip-game | 旧游戏机式音色 | Chiptune console timbres | unmistakable early-console square and triangle wave melodies with rapid chip arpeggios and primitive noise-channel drums | synthesized instrumental :: electronic instrumental music with simple synthesized melodies
percussion-loop | 互动配乐式循环 | Looping game-score timbres | a short seamless game-like instrumental loop with a persistent sequenced ostinato, repeated cue-like returns and game-synth timbres | repetitive instrumental :: instrumental music with repeated melodic phrases and a regular beat
game-battle | 游戏战斗式编配 | Video-game battle arrangement | tightly looped urgent battle-score riffs with rapid sequenced string ostinatos, emphatic synthetic brass hits and driving game-like percussion | energetic instrumental :: energetic instrumental music with strings, synthesizers and drums
cinematic-build | 电影配乐式推进 | Cinematic dramatic build | a cinematic tension arc with rising orchestral ostinatos, a large crescendo, low impact booms and a clear dramatic release | dynamic orchestral :: instrumental music with changing loudness and orchestral instruments
orchestral-score | 影视管弦叙事线索 | Orchestral film-score arrangement | narrative orchestral cue with recurring character-like motifs, synchronized dramatic hits and changing strings, brass and woodwind sections | orchestral concert :: an orchestral concert performance
suspense-score | 悬疑氛围声线索 | Electronic suspense underscore | a sparse suspense underscore with isolated sub-bass pulses, dissonant drones, eerie bowed textures and long deliberate gaps | ambient electronic :: quiet ambient electronic music with sustained tones
anime-score | 动画配乐式编配 | Anime-score arrangement | expressive anime-score-like melody moving between intimate piano, emotional bowed strings and a sudden bright band or orchestral swell | melodic instrumental :: melodic instrumental music with piano and strings
musical-theatre | 音乐剧式演唱 | Musical-theatre singing | clearly theatrical character singing with dialogue-like phrasing, dramatic ensemble responses and synchronized stage-orchestra accents | orchestral pop :: a pop singer accompanied by a band or orchestra
    """),
    *scene_group("地区与传统", """
east-asian-ensemble | 东亚丝竹式编制 | East Asian silk-and-bamboo ensemble | interwoven bamboo flute, bowed erhu-like strings and bright plucked zithers with sliding ornamented pentatonic phrases | acoustic flute and strings :: acoustic instrumental music with flute and string instruments
modal-improv | 调式即兴线索 | Raga-like modal improvisation | free raga-like melodic improvisation with ornamented sitar or voice, microtonal bends, a continuous tanpura drone and responsive tabla patterns | acoustic improvisation :: improvised acoustic instrumental music with melody and percussion
interlocking-gongs | 锣鼓与金属琴交错合奏 | Interlocking gamelan ensemble | clearly pitched gamelan-like gongs and metallophones playing overlapping cyclic interlocking parts with resonant metallic decay | tuned percussion :: rhythmic instrumental music with bells and percussion
layered-hand-drums | 多层手鼓舞曲线索 | Interlocking hand-drum ensemble | an acoustic djembe-like hand-drum ensemble with interlocking polyrhythms, sharp slap tones, deep hand strikes and group-response accents | rhythmic percussion :: music with drums and syncopated percussion
japanese-traditional | 日式传统器乐编制 | Japanese traditional ensemble | sharply plucked shamisen or koto, breathy shakuhachi bamboo flute and resonant taiko strokes in a traditional Japanese-like ensemble | acoustic instrumental :: acoustic music with plucked strings, flute and percussion
chinese-opera | 戏曲式唱腔锣鼓 | Chinese opera | piercing ornamented opera-like Chinese singing punctuated by sharp clappers, gongs and tightly accented theatrical drum patterns | theatrical singing :: theatrical singing with instrumental accompaniment
arabic-ensemble | 乌德琴与调式花腔编制 | Arabic maqam ensemble | oud and qanun-like plucked ornaments under melismatic Arabic-like singing, maqam-style turns and darbuka hand-drum patterns | acoustic singing :: acoustic singing accompanied by plucked strings and percussion
celtic-session | 凯尔特舞曲式合奏 | Celtic folk session | fast unison fiddle and tin-whistle dance tunes with accordion or pipes and a strongly lilting jig or reel rhythm | acoustic folk :: folk instrumental music with fiddle and wind instruments
flamenco | 弗拉门戈式演唱与击掌 | Flamenco singing and handclaps | sharply rasgueado-strummed nylon guitar, accented palmas handclaps, heel-like taps and raw melismatic cante singing | acoustic guitar singing :: acoustic guitar music with singing and percussion
balkan-brass | 巴尔干铜管舞曲编制 | Balkan brass dance ensemble | a bright fast brass-and-reed folk ensemble with tuba bass, a busy snare and strongly asymmetric dance-meter accents | brass band :: brass-band music with drums and wind instruments
andean-ensemble | 安第斯排箫式编制 | Andean panpipe ensemble | breathy panpipe and quena-like melodies above rapid charango strumming and deep bombo-like drum strokes | acoustic folk :: acoustic folk music with flute, plucked strings and drums
west-african-strings | 西非竖琴式弹唱 | West African kora singing | flowing interwoven kora-like harp or ngoni-like plucked patterns with griot-style ornamented singing and woody acoustic resonance | acoustic plucked-string singing :: acoustic singing with plucked string accompaniment
brazilian-carnival | 桑巴游行式打击编制 | Samba carnival percussion | many interlocking samba percussion parts with deep surdo pulses, busy tamborim strokes, shaker wash and cuica-like squeals | percussion dance :: dance music with multiple percussion instruments
mongolian-overtones | 呼麦与持续低音 | Mongolian throat singing | a clearly audible low sustained vocal drone with whistling overtone harmonics and resonant throat-singing formants | sustained low singing :: low-pitched singing with sustained notes
south-asian-film | 南亚歌舞式编制 | South Asian film-song arrangement | highly ornamented film-song singing with dhol or tabla-like drums, bright string flourishes and strong dance-and-chorus call patterns | rhythmic orchestral pop :: melodic pop singing with strings and rhythmic percussion
    """),
    *scene_group("演唱与集体表演", """
call-and-response | 集体应答演唱线索 | Group call-and-response singing | a clearly alternating solo sung call answered by a separate group chorus in repeated short exchanges | lead and backing vocal :: music with lead vocals and backing harmonies
processional | 行进与仪式式音响 | Ceremonial marching sounds | a deliberate marching processional pulse with evenly spaced ceremonial drum strokes, brass or group chant and repeated measured calls | rhythmic ensemble :: rhythmic ensemble music with drums and voices
voice-recitation | 诵唱式声音线索 | Recited unison chanting | sustained unison recited chanting with narrow repeating pitch patterns, a vocal drone and few clearly articulated instrumental parts | sustained singing :: singing with repeated notes and soft accompaniment
family-chorus | 齐唱与唱游线索 | Family sing-and-play chorus | simple children's or family-group unison singing with repeated nursery-like phrases, handclaps and audible playful group responses | group singing :: a singer performing a simple melodic song
sing-along | 儿童齐唱线索 | Children's nursery chorus | clearly audible children's voices singing a short familiar nursery-style tune together in straightforward unison | group singing :: multiple singers performing a repeated melody
movement-song | 唱游口令线索 | Movement-command play songs | spoken or sung movement commands repeatedly answered by group claps, stomps and a simple stop-and-start play rhythm | upbeat singing :: an upbeat song with a regular rhythm and singing
gospel-choir | 福音式合唱应答 | Gospel choir responses | an impassioned solo gospel-like lead answered by a large harmonized choir with Hammond organ and strong handclap accents | soulful backing-vocal :: soulful singing with backing voices, keyboard and drums
chamber-style | 室内乐编配线索 | Chamber ensemble arrangement | a small exposed acoustic chamber ensemble with individually audible bowed-string or woodwind lines, shared room resonance and flexible interweaving phrasing | acoustic instrumental :: instrumental music performed by acoustic musicians
    """),
    *scene_group("独立与另类制作", """
diy-band | DIY／独立乐队录音线索 | DIY indie-band production | a raw indie-band recording with loosely played live drums, exposed guitar and bass layers, intimate room reflections and an unpolished vocal mix | polished studio rock :: a polished studio band recording with electric guitars, bass, drums and vocals
bedroom-pop | 卧室流行制作线索 | Bedroom pop production | very close softly sung vocals over dry homemade drum loops, warm small-keyboard sounds and audibly intimate low-fidelity overdubs | studio pop :: a studio pop song with lead singing, keyboards and electronic drums
emo-dynamics | Emo／另类情绪化编配 | Emo alternative-rock dynamics | strained expressive singing with clean arpeggiated guitars suddenly opening into heavy distorted choruses and emphatic live drums | alternative rock :: a rock band with sung vocals, electric guitars, bass and live drums
goth-electronic | 暗色电子哥特音色 | Darkwave and goth electronic sound | deep detached singing over icy chorus-treated bass, minor-key synth sequences, spacious drum-machine hits and a cold gothic texture | electronic pop :: synthesized pop music with a bassline, sung vocals and electronic drums
postrock-build | 器乐后摇式推进 | Instrumental post-rock builds | long instrumental electric-guitar layers gradually rising from sparse delicate arpeggios into a loud sustained crescendo with expansive live drums | instrumental rock :: guitar-based instrumental music with varying loudness and a drum beat
plugg-keys | Plugg／卧室说唱键盘语汇 | Plugg and pluggnb production | dreamy plugg-style trap production with sugary chiming keyboard leads, wide nostalgic rompler pads, simple soft claps and loose ticking hi-hats | contemporary trap :: hip-hop or trap production with a repeating keyboard melody, electronic bass and a drum beat
ambient-immersive | 沉浸式环境声场 | Immersive ambient soundscapes | slowly evolving spatial pads and drones with long overlapping reverb tails, almost no articulated beat and deliberately suspended harmonic movement | electronic instrumental :: quiet instrumental electronic music with sustained chords and melodic phrases
experimental-collage | Glitch 数字拼贴语汇 | Glitch and experimental digital collage | sharply sliced granular fragments, fractured micro-loops, glitch clicks and sudden discontinuous changes of digitally rearranged sound texture | electronic instrumental :: instrumental electronic music with synthesizers, percussion and repeated melodies
    """),
)

CATALOG = {tag.label: tag for tag in (*STYLES, *SCENES)}
if len(CATALOG) != len(STYLES) + len(SCENES) or len({tag.id for tag in CATALOG.values()}) != len(CATALOG):
    raise ValueError("Music tag labels and identifiers must be unique across vocabularies.")
DEFAULT_TAGS = {label: tag.description for label, tag in CATALOG.items()}
ALIASES = {name.casefold(): tag.label for tag in CATALOG.values() for name in (tag.label, *tag.aliases)}
def canonical_label(label):
    return ALIASES.get(label.casefold(), label)


def limit_scene_candidates(candidates):
    remaining = 3
    results = []
    for row in candidates:
        if row.get("kind") == "scene":
            if not remaining:
                continue
            remaining -= 1
        results.append(row)
    return results


def rank_candidates(labels, scores, genres):
    support = {}
    for row in genres:
        family = row.get("full_label", "").split("---", 1)[0]
        support[family] = max(support.get(family, 0), row["coverage"] / 100)
    ranked = []
    for label, score in zip(labels, scores):
        tag = CATALOG.get(label)
        row = {"label": label, "score": round(float(score), 3),
               "kind": tag.kind if tag else "style", "evidence": "CLAP 音频相似度"}
        bonus = 0
        if tag:
            row.update(id=tag.id, family=tag.family, branch=tag.branch)
            if tag.kind == "style":
                bonus = .025 * support.get(tag.family, 0)
        ranked.append((float(score) + bonus, row))
    ranked.sort(key=lambda item: -item[0])
    return limit_scene_candidates(row for _, row in ranked)
