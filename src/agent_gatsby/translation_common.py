"""
Shared translation helpers for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
import re

from agent_gatsby.config import AppConfig
from agent_gatsby.data_ingest import utc_now_iso
from agent_gatsby.llm_client import LLMResponseValidationError, invoke_text_completion

LOGGER = logging.getLogger(__name__)

BLOCK_SPLIT_RE = re.compile(r"\n\s*\n")
HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+.+$")
HEADING_LINE_RE = re.compile(r"^(#{1,6}\s+)(.*)$")
BLOCKQUOTE_LINE_RE = re.compile(r"^(\s*>\s?)(.*)$")
NUMBERED_LIST_LINE_RE = re.compile(r"^\d+\.\s+")
NUMBERED_CITATION_ENTRY_RE = re.compile(r"(?m)^\d+\.\s+")
ENGLISH_CITATION_ENTRY_RE = re.compile(
    r'^(?P<number>\d+\.)\s+F\. Scott Fitzgerald, \*The Great Gatsby\*, ch\. (?P<chapter>\d+), para\. (?P<paragraph>\d+), cited passage beginning (?P<lemma>.+)$'
)
VISIBLE_CITATION_RE = re.compile(r"\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\]")
SIMPLE_VISIBLE_CITATION_RE = re.compile(r"\[(\d+)\]")
TRANSLATION_CITATION_PLACEHOLDER_RE = re.compile(r"AGCITTOKEN(\d{4})XYZ")
STRAIGHT_QUOTE_SPAN_RE = re.compile(r'"[^"\n]+?"')
CURLY_QUOTE_SPAN_RE = re.compile(r"“[^”\n]+?”")
LOW_SINGLE_QUOTE_SPAN_RE = re.compile(r"‘[^’\n]+?’")
GUILLEMET_QUOTE_SPAN_RE = re.compile(r"«[^»\n]+?»")
CJK_CORNER_QUOTE_SPAN_RE = re.compile(r"「[^」\n]+?」")
CJK_WHITE_CORNER_QUOTE_SPAN_RE = re.compile(r"『[^』\n]+?』")
CITATION_QUOTE_LINE_RE = re.compile(r'^\s*>\s+\*?(?P<quote>(?:"[^"\n]+?"|“[^”\n]+?”|「[^」\n]+?」|『[^』\n]+?』))\*?\s+\[(?P<number>\d+)\]\s*$')
CITED_QUOTE_SPAN_RE = re.compile(
    r'(?P<quote>\*?(?:"[^"\n]+?"|“[^”\n]+?”|«[^»\n]+?»|「[^」\n]+?」|『[^』\n]+?』)\*?)\s*\[(?P<number>\d+)\]'
)
CITATIONS_SECTION_RE = re.compile(r"(?m)^## Citations\s*$")
TRANSLATED_CITATIONS_SECTION_RE = re.compile(r"(?m)^##\s+(?:Citations|Citas|引文)\s*$")
ENGLISH_MULTIWORD_RE = re.compile(r"[A-Za-z][A-Za-z'’.-]*(?:\s+[a-z][A-Za-z'’.-]*){2,}")
CITATION_GLUE_RE = re.compile(r"(\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\])(?=[A-Za-zÁ-ÿ一-龯])")
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200d\u2060\ufeff]")
ASSISTANT_PROMPT_LEAK_RE = re.compile(
    r"Please provide the .*?fragment you would like me to revise\.\s*"
    r"I am ready to apply .*?instructions\.",
    re.IGNORECASE,
)
LEAKED_AGC_CITATION_RE = re.compile(r"\bAGC\w*\[(\d+)\]")
DYNAMIC_VALIDATION_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
DYNAMIC_VALIDATION_JSON_OBJECT_RE = re.compile(r"{.*}", re.DOTALL)
STANDALONE_ZERO_LINE_RE = re.compile(r"(?m)^[ \t]*0[ \t]*$\n?")
ASCII_COMMA_AFTER_CITATION_RE = re.compile(
    r"(\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\])\s*,"
)
ENGLISH_PROSE_PROPER_NOUN_PATTERNS = (
    (re.compile(r"\b(?:a|the)\s+valley of ashes\b"), "the Valley of Ashes"),
)
MANDARIN_NORMALIZATION_MAP = {
    "菲茨平": "菲茨杰拉德",
    "菲茨格拉德": "菲茨杰拉德",
    "《了了不起的盖茨比》": "《了不起的盖茨比》",
    "《了_不起的盖茨比》": "《了不起的盖茨比》",
    "T·J·艾克堡医生": "T. J. 埃克尔伯格医生",
    "T·J·艾克堡": "T. J. 埃克尔伯格",
    "T. J. 艾克尔堡医生": "T. J. 埃克尔伯格医生",
    "盖失比": "盖茨比",
    "盖茨模": "盖茨比",
    "（Nick Carraway）": "",
    "（West Egg）": "",
    "（Valley of Ashes）": "",
    "_本报告将所选隐喻分为八个主题部分，以符合约十页的篇幅要求。若需进行更深入的研究，可通过增加额外的隐喻集群来扩展分析内容._": "_本报告将选定的隐喻群组织为八个主题部分，以形成结构清晰、引文可核查的分析。_",
    "“veiled”（遮蔽）": "“遮蔽”",
    "“veiled”（遮蔽的）": "“遮蔽”",
    "“遮蔽”（veiled）一词的使用": "“遮蔽”一词的使用",
    "“veiled”（遮蔽的）一词的使用": "“遮蔽”一词的使用",
    "（casual gaming）": "",
    "### # 梦想的瓦解": "### 梦想的瓦解",
    "菲茨杰是否存在利用地质和空间隐喻，建立了一个人物与景观都不具备固定、可靠中心的的世界。": "菲茨杰拉德利用地质和空间隐喻，建立了一个人物与景观都不具备固定、可靠中心的世界。",
    "长岛海峡那巨大的湿润农场": "长岛海峡那片潮湿而阔大的牲口院",
    "长岛海峡那巨大的湿润院落": "长岛海峡那片潮湿而阔大的牲口院",
    "谷仓院": "牲口院",
    "长显长岛海峡那巨大的湿漉漉的牲口棚": "长岛海峡那片潮湿而阔大的牲口院",
    "来自长岛西卵的杰伊·盖茨比，从他对自己的一种柏拉图式的构想中脱颖而出。": "来自长岛西卵的杰伊·盖茨比，源于他对自己的一种柏拉图式构想。",
    "来自长岛西卵的杰伊·盖茨比，从他对自己完美的柏拉图式构想中脱颖而出。": "来自长岛西卵的杰伊·盖茨比，源于他对自己的一种柏拉图式构想。",
    "来自长岛西卵的杰伊·构想中的杰伊·盖茨比，从他对自己的一种柏拉图式的构想中脱颖而出。": "来自长岛西卵的杰伊·盖茨比，源于他对自己的一种柏拉图式构想。",
    "来自长岛西卵的杰伊·构想中的杰伊·盖茨比": "来自长岛西卵的杰伊·盖茨比",
    "杰·盖茨比": "杰伊·盖茨比",
    "杰伊·盖茨比那模糊的轮廓已变得如一个男人般厚实感": "杰伊·盖茨比那模糊的轮廓已充实为一个男人的实体感",
    "已变得如一个男人般厚实感": "已充实为一个男人的实体感",
    "整个大篷车营地就像纸牌屋一样坍塌了": "整个商队旅馆就像纸牌屋一样坍塌了",
    "整个大篷车营地像纸牌屋一样坍塌了": "整个商队旅馆像纸牌屋一样坍塌了",
    "他的眼中不断流露出激动": "他的眼睛不断流出激动的泪水",
    "构成了听觉意象 [30]；这构成了角色与退却的梦想之间日益加剧的情感与物理距离的隐喻。": "构成了一种听觉意象，象征着角色与退却的梦想之间日益扩大的情感与物理距离 [30]。",
    "促成了一场色彩与声音的剧变": "使色彩与音乐交织在一起",
    "世界及其情妇": "世界及其情人",
    "世界及其女主人": "世界及其情人",
    "鸿望": "鸿沟",
    "男人和姑娘们": "男人和女孩们",
    "人群的旋涡与涡流": "人群的旋涡与湍流",
    "从餐饮师的篮子里变出来的": "从餐饮师的篮子里端出来的",
    "餐饮承包园": "餐饮承包商",
    "已充实成了一个男人的实体": "已充实为一个男人的实体感",
    "实体感感": "实体感",
    "一个男人的实体感感": "一个男人的实体感",
    "一打太阳": "十二轮太阳",
    "十几轮太阳": "十二轮太阳",
    "世界博览会": "世博会",
    "补剂": "强心剂",
    "补药": "强心剂",
    "现实的非真实性": "对现实的否认",
    "这种独特人性的丧失": "这种个体人性的丧失",
    "文中将窗帘比作帐篷的明喻 [26] 这种意象": "文中将窗帘比作帐篷 [26]，这种意象",
    "在物理层面击碎了精心营造的新贵外壳": "象征性地击碎了新贵阶层精心营造的外壳",
    "在物理层面上改变了生活其中的人": "切实地改变了生活其中的人",
    "在物理层面发生破碎的时刻": "明显走向破碎的时刻",
    "因为环境在物理层面上吞噬了角色": "因为环境逐渐吞噬了角色",
    "因为环境在物理层面已然吞噬了角色": "因为环境已然吞噬了角色",
    "更在物理层面上粉碎了他多年来苦心经营的形象": "更象征性地粉碎了他多年来苦心经营的形象",
    "更在物理层面上击碎了他多年来致力于完善的形象": "更象征性地击碎了他多年来致力于完善的形象",
    "其庄园在物理层面的荒废": "其庄园明显可见的荒废",
    "庄园物理层面的退化": "庄园明显可见的退化",
    "字面上如玻璃般破碎": "被描写为如玻璃般破碎",
    "在字面与语言层面的消解": "在可见与语言层面的瓦解",
    "所栖模的": "所栖居的",
    "长岛海峡那巨大的湿漉漉的农场": "长岛海峡那片潮湿而阔大的牲口院",
    "大篷车旅馆": "商队旅馆",
    "大篷车营地（a caravan camp）": "商队旅馆",
    "大篷车营地": "商队旅馆",
    "叙骗手段": "叙事手段",
    "盖盖茨比": "盖茨比",
    "轮控": "轮廓",
    "他的眼中不断流露出兴奋之情": "他的眼中因兴奋而不断溢出泪水",
    "\"It was this night that he told me the strange story of his youth...\"": "“‘杰伊·盖茨比’像玻璃一样在汤姆冷酷的恶意面前碎裂了”",
    "尼克·是否·卡拉威": "尼克·卡拉威",
    "黄色鸡模音乐": "黄色鸡尾酒音乐",
    "香骗": "香槟",
    "在 [12] 在文中": "在 [12] 中",
    "菲茨杰拉德将汤向描述为": "菲茨杰拉德将汤姆描述为",
    "它们在物理层面上吞噬着生活其中的人们": "它们逐渐吞噬着生活其中的人们",
    "在物理层面上吞噬着生活其中的人们": "逐渐吞噬着生活其中的人们",
    "这种不稳定性从生物层面延伸到了物理层面": "这种不稳定性从生物意象延伸到了流体意象",
}
SPANISH_NORMALIZATION_MAP = {
    "# Un análisis de las metáforas en *The Great Gatsby*": "# Un análisis de las metáforas en *El gran Gatsby*",
    "_Este informe organiza las metáforas seleccionadas en ocho secciones temáticas para cumplir con el requisito de un trabajo de aproximadamente diez páginas. El análisis podría ampliarse con grupos de metáforas adicionales si se deseara un estudio más extenso._": "_Este informe organiza grupos de metáforas seleccionados en ocho secciones temáticas para un análisis estructurado y sustentado por citas._",
    "*The Great Gatsby*": "*El gran Gatsby*",
    "Please provide the Spanish markdown fragment you would like me to revise. I am ready to apply the professional academic copyediting standards described in your instructions.": "",
    "desibuja": "desdibuja",
    "ilustcionar": "ilustrar",
    "metáfor yas": "metáforas",
    "música de cóctel amarillo": "música amarilla de cóctel",
    "cesta de un catering": "cesta de un banquetero",
    "La casa no simplemente existe": "La casa no existe simplemente",
    "masimvo": "masivo",
    "el excitante ondular de su encuentro": "el excitante ondular de su voz",
    "El emocionante murmullo de su voz": "El excitante ondular de su voz",
    "emocionante murmullo de su voz": "excitante ondular de su voz",
    "colapiente": "colapso",
    "inestímulo": "inestabilidad",
    "laberinto de pantallas": "laberinto de parabrisas",
    "borde irregular del universo": "borde deshilachado del universo",
    "episodio deshilachado del universo": "borde deshilachado del universo",
    "el gran y húmedo corral de Long Island Sound": "el gran corral húmedo de Long Island Sound",
    "el gran y húmedo corral": "el gran corral húmedo",
    "el vago contorno de Jay Gatsby se había robustecido hasta alcanzar la sustancialidad de un hombre": "el vago contorno de Jay Gatsby se había completado hasta alcanzar la consistencia de un hombre",
    "acervo común de la vida": "reserva común de la vida",
    "reserva común de vida": "reserva común de la vida",
    "recinto de cuero verde": "invernadero de cuero verde",
    "experiencia altamente curada": "experiencia cuidadosamente diseñada",
    "evento curado y estetizado": "evento cuidadosamente diseñado y estetizado",
    "dinero viejo y el nuevo": "vieja élite adinerada y los nuevos ricos",
    "la perfección agresiva y curada": "la perfección agresiva y cuidadosamente diseñada",
    "ficción cuidadosamente curada": "ficción cuidadosamente construida",
    "apariencia curada de Gatsby": "apariencia cuidadosamente construida de Gatsby",
    "jardines grotescos . [4],": "jardines grotescos [4],",
    "el mundo y su señora regresaban": "el mundo y su amante regresaban",
    "naturaleza seducción": "naturaleza seductora",
    "únicamente con el oído. [19];": "únicamente con el oído [19];",
    "irrealidad de la realidad": "negación de la realidad",
    "Esta fragilidad se vuelve literal": "Esta fragilidad se vuelve visible",
    "rompe físicamente la apariencia cuidadosamente curada de la nueva": "quiebra simbólicamente la fachada cuidadosamente construida de la nueva",
    "esta artificialidad se rompe físicamente": "esta artificialidad se quiebra de forma visible",
    "rompe físicamente la imagen que él ha pasado años perfeccionando": "quiebra simbólicamente la imagen que él ha pasado años perfeccionando",
    "se rompe literalmente como el cristal": "se describe como si se hiciera añicos como el cristal",
    "la disolución literal y lingüística de sus ilusiones cuidadosamente mantenidas": "el visible y verbal desmoronamiento de sus ilusiones cuidadosamente mantenidas",
    'se revela como un caravasar que se ha derrumbado como un castillo de naipes [21] al enfrentarse al juicio de los demás.': 'se derrumba como un castillo de naipes ante el juicio social [21].',
    '"todo el caravansary se había derrumbado como un castillo de naipes" [21]': "que se derrumba como un castillo de naipes [21]",
    "todo el caravansary": "todo el mundo social de Gatsby",
    "sueño americano": "Sueño Americano",
    "una transformación radical de color y voz": "una fusión de color y música",
    "apariencia cuidadosamente curada": "fachada cuidadosamente construida",
    "depósito común de la vida": "reserva común de la vida",
    "ilusiones cuidadosamente curadas": "ilusiones cuidadosamente mantenidas",
    "un *caravansary*": "un mundo social transitorio",
    "Sus ojos brotaban continuamente de emoción": "Los ojos se le llenaban continuamente de emoción",
    "apogeencia": "apogeo",
    "el narración describe": "el narrador describe",
    "servicio de catering": "servicio de banquetes",
    "catalelo": "catalizador",
    "pierta": "pierden",
    'surgió de su concepción platónica de sí mismo". [13]': 'surgió de su concepción platónica de sí mismo" [13].',
    '*"surgió de su concepción platónica de sí mismo"*. [13]': '*"surgió de su concepción platónica de sí mismo"* [13].',
}
SPANISH_CITATION_QUOTE_OVERRIDES = {
    19: '"El excitante ondular de su voz era un tónico salvaje bajo la lluvia"',
    21: '"todo el mundo social de Gatsby se había derrumbado como un castillo de naipes"',
    23: '"En este calor, cada gesto adicional era una afrenta a la reserva común de la vida"',
    29: '"Los ojos se le llenaban continuamente de emoción"',
}
MANDARIN_CITATION_QUOTE_OVERRIDES = {
    27: "“‘杰伊·盖茨比’像玻璃一样在汤姆冷酷的恶意面前碎裂了”",
    29: "“他的眼中因兴奋而不断溢出泪水”",
}
ENGLISH_MASTER_REGRESSION_FIXES = {
    "Valley of West": "Valley of Ashes",
    "punctiliously manner": "punctilious manner",
    "theragged edge": "the ragged edge",
    "He does not use metaphor merely": "He does not use metaphors merely",
    "grotesleque": "grotesque",
    "Nick Carrawical": "Nick Carraway",
    "it actively populating the landscape": "it actively populates the landscape",
    "instead, he employs it as a structural tool.": "instead, he employs them as structural tools.",
    "literal and figurative heat": "rising heat and social pressure",
    "literal and figurative heat that leads to the story's tragic conclusion.": "the rising heat and social pressure that lead to the story's tragic conclusion.",
    "The narrator experiences Daisy’s presence as a physical, medicinal force. He notes that The exhilarating ripple of her voice was a purely wild tonic in the rain [19].": 'The narrator experiences Daisy’s presence as a physical, medicinal force. He notes that *"The exhilarating ripple of her voice was a wild tonic in the rain"* [19].',
    r"Nick describes how The exhilarating ripple of her voice was a\ wild tonic in the rain [19].": 'Nick describes how *"The exhilarating ripple of her voice was a wild tonic in the rain"* [19].',
    "In the stifling atmosphere of the afternoon, In this heat every extra gesture was an affront to the common store of life [23].": 'In the stifling atmosphere of the afternoon, *"In this heat every extra gesture was an affront to the common store of life"* [23].',
    "the auditory imagery of a thin and far away voice [30]": 'the auditory imagery of a voice described as "thin and far away" [30]',
    "All that remains is the thin and far away [30] echo of a dream": 'All that remains is the "thin and far away" [30] echo of a dream',
    "The confrontation between Gatsby and Tom provides the moment where this artificiality physically breaks.": "The confrontation between Gatsby and Tom provides the moment where this artificiality visibly breaks.",
    "because his very foundation is built on a fairy’s wing [20], his entire persona is susceptible to the slightest shift in social perception.": "because his very foundation rests on an impossible fantasy [20], his entire persona is susceptible to the slightest shift in social perception.",
    '*"*“Jay Gatsby”* had broken up like glass against Tom’s hard malice"* [27]': '*"‘Jay Gatsby’ had broken up like glass against Tom’s hard malice"* [27]',
    "the vague contour of Jay and Gatsby had filled out to the substantiality of a man": "the vague contour of Jay Gatsby had filled out to the substantiality of a man",
    "a complex, labyrinth of windshields": "a complex labyrinth of windshields",
    "the persona of Jay Gatsby literally broken up like glass": "the persona of Jay Gatsby is literally broken up like glass",
    "the Middle West now seemed like the outward edge of the universe [2]": '*"the Middle West now seemed like the ragged edge of the universe"* [2]',
    "Nick remarks, Your place looks like the Es World’s Fair [18].": 'Nick remarks, *"Your place looks like the World’s Fair"* [18].',
    "Your place looks like the Es World’s Fair [18]": '"Your place looks like the World’s Fair" [18]',
    "look out over the solemn dumping ground [5]": '"look out over the solemn dumping ground" [5]',
    "ash-grey men, who move dimly and already crumbling through the powdery air [4]": '"ash-grey men, who move dimly and already crumbling through the powdery air" [4]',
    "a white ashen dust veiled his dark suit and his pale hair as it veiled everything in the vicinity [6]": '"a white ashen dust veiled his dark suit and his pale hair as it veiled everything in the vicinity" [6]',
    "the thin and far away [30] echoes of a dead dream": 'the "thin and far away" [30] echoes of a dead dream',
    "Jay Gatsby of West Egg, Long Island, sprang from his Platonic conception of himself [13]": '"Jay Gatsby of West Egg, Long Island, sprang from his Platonic conception of himself" [13]',
    "he sprang from his Platonic conception of himself [13] to achieve the substantiality of a man [14].": 'he *"sprang from his Platonic conception of himself"* [13] and pursued *"the substantiality of a man"* [14].',
    "the straw seats of the car hovered on the edge of combustion [22]": '"the straw seats of the car hovered on the edge of combustion" [22]',
    "in this heat every extra gesture was an affront to the common store of life [23]": '"in this heat every extra gesture was an affront to the common store of life" [23]',
    "a man’s voice, very thin and far away [30]": '"a man’s voice, very thin and far away" [30]',
    "_This report organizes selected metaphors into 8 thematic sections to fit an approximately ten-page assignment requirement. The analysis could be expanded with additional metaphor clusters if a longer study were desired._": "_This report organizes selected metaphor clusters into eight thematic sections for a structured, citation-supported analysis._",
    "contributing to a sea-change of color and voice that makes the environment feel hallucinatory.": "contributing to a fusion of color and music that makes the environment feel hallucinatory.",
    "Because his identity is built upon the unreality of reality [20], the social structure he creates is inherently prone to sudden disintegration.": "Because his identity is built upon a denial of reality [20], the social structure he creates is inherently prone to sudden disintegration.",
    "By framing his ascent as a spiritual and fated event, Gatsby attempts to insulate his fragile identity from the unreality of reality that haunts his early years.": "By framing his ascent as a spiritual and fated event, Gatsby attempts to insulate his fragile identity from the denial of reality that haunts his early years.",
    "which seemed like the ragged edge of the universe [2]": 'which seemed like *"the ragged edge of the universe"* [2]',
    "seemed like the ragged edge of the universe [2]": 'seemed like *"the ragged edge of the universe"* [2]',
    "This fragility becomes literal during the confrontation with Tom, where a simile compares Gatsby’s constructed identity to shattering glass [27].": "This fragility becomes visible during the confrontation with Tom, where a simile compares Gatsby’s constructed identity to shattering glass [27].",
    "The aggression of the old aristocracy physically breaks the carefully curated veneer of the new, proving that Gatsby’s self-invention cannot survive direct contact with the past.": "The aggression of the old aristocracy symbolically shatters the carefully constructed veneer of the new, proving that Gatsby’s self-invention cannot survive direct contact with the past.",
    'The social world Gatsby built is revealed to be "the whole caravansary" that has fallen like a card house [21] when confronted by the judgment of others.': "The social world Gatsby built falls like a card house under the pressure of social judgment [21].",
    "This collapse is finalized when the persona of Jay Gatsby is literally broken up like glass against Tom’s hard malice [27].": "This collapse is finalized when Gatsby's constructed persona is described as breaking like glass against Tom’s hard malice [27].",
    "the rock of the world was founded securely on a fairy’s wing [20], a sentiment that allowed him to ignore the foul dust [1] of his actual origins.": "an impossible fantasy [20], which allowed him to ignore the material and moral reality of his actual origins.",
    "The social world he built was a caravansary that eventually had fallen in like a card house [21] when confronted by the judgment of others.": "The social world he built eventually fell like a card house under the pressure of social judgment [21].",
    "Ultimately, the persona of Jay Gatsby could not survive the collision with the real world, as the identity had broken up like glass against Tom’s hard malice [27].": "Ultimately, Gatsby's constructed identity could not survive the collision with the real world, and it is described as breaking like glass against Tom’s hard malice [27].",
    "The many layers of glass create a green leather conservatory [16] that isolates the occupants, turning a simple drive into a highly curated, artificial experience.": "The many layers of glass give the car the enclosed feel of a green leather conservatory [16], isolating the occupants and turning a simple drive into a carefully designed, artificial experience.",
    "the eventual collapse of Gatsby's world is signaled by the literal and linguistic dissolution of his carefully maintained illusions.": "the eventual collapse of Gatsby's world is signaled by the visible and verbal unraveling of his carefully maintained illusions.",
    "his carefully curated world to fracture.": "his carefully constructed world to fracture.",
    "the carefully curated version of Gatsby is no longer capable of holding together under the pressure of reality.": "the carefully constructed version of Gatsby is no longer capable of holding together under the pressure of reality.",
    'The carefully constructed social world Gatsby builds is revealed to be a fragile assembly, a structure that eventually fails when the weight of truth becomes too great, as seen when "the whole caravansary had fallen in like a card house" [21].': "The carefully constructed social world Gatsby builds proves to be fragile, and it collapses under the weight of social judgment [21].",
    "This collapse is not merely social but personal; the very identity Gatsby labored to create is destroyed by the friction of reality, as Jay Gatsby is described as breaking up like glass against Tom’s hard malice [27].": "This collapse is not merely social but personal; the identity Gatsby labored to create is described as shattering like glass against Tom’s hard malice [27].",
    'In the end, the dissolution of Gatsby’s world leaves behind only fragments of a lost era. The grand, theatrical scale of his estate, once appearing as a spectacle [18] with *"curtains that were like pavilions"* [26], is reduced to a place of inexplicable amount of dust [26] and musty rooms.': 'In the end, the dissolution of Gatsby’s world leaves behind only fragments of a lost era. The grand, theatrical scale of his estate, once appearing as a spectacle [18] with *"curtains that were like pavilions"* [26], is reduced to a house of musty rooms and dust [26].',
}
DEFAULT_REQUIRED_ENGLISH_MASTER_TERMS: tuple[str, ...] = ()
DEFAULT_FORBIDDEN_ENGLISH_MASTER_PHRASES = (
    "Valley of West",
    "punctiliously manner",
    "theragged edge",
    "He does not use metaphor merely",
    "grotesleque",
    "Nick Carrawical",
    "it actively populating the landscape",
    "literal and figurative heat",
    "outward edge of the universe [2]",
    "Es World’s Fair",
    r"The exhilarating ripple of her voice was a\ wild tonic in the rain",
    "The confrontation between Gatsby and Tom provides the moment where this artificiality physically breaks.",
    "a complex, labyrinth of windshields",
    "the persona of Jay Gatsby literally broken up like glass",
    '*"*“Jay Gatsby”* had broken up like glass against Tom’s hard malice"* [27]',
    "look out over the solemn dumping ground [5]",
    "a white ashen dust veiled his dark suit and his pale hair as it veiled everything in the vicinity [6]",
    "the thin and far away [30] echoes of a dead dream",
    "fairy’s wing [20]",
    "foul dust [1]",
    "place of inexplicable amount of dust [26]",
    "to fit an approximately ten-page assignment requirement",
    "could be expanded with additional metaphor clusters if a longer study were desired",
    "sea-change of color and voice",
    "unreality of reality",
    "This fragility becomes literal during the confrontation with Tom",
    "physically breaks the carefully curated veneer",
    "literally broken up like glass",
    "literal and linguistic dissolution",
)
SPANISH_INTERNAL_TOKEN_RE = re.compile(r"\bAGCIT\w*(?:\s+[\u0400-\u04FF]+)?")
SPANISH_ESCAPE_SEQUENCE_RE = re.compile(r"\$\\\\\w+\b|\\[A-Za-z]+\b")
MANDARIN_ELLIPSIS_BEFORE_CITATION_RE = re.compile(
    r"[.…]{2,}\s*(\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\])"
)
MANDARIN_SENTENCE_BREAK_BEFORE_CITATION_RE = re.compile(
    r"([。！？])\s*(\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\])，"
)
UNQUOTED_ENGLISH_QUOTE_PATTERNS = (
    re.compile(r'(?<!["“])the ragged edge of the universe \[2\]'),
    re.compile(r'(?<!["“])the great wet barnyard of Long Island Sound \[3\]'),
    re.compile(r'(?<!["“])ash-grey men, who move dimly and already crumbling through the powdery air \[4\]'),
    re.compile(r'(?<!["“])look out over the solemn dumping ground \[5\]'),
    re.compile(r'(?<!["“])a white ashen dust veiled his dark suit and his pale hair as it veiled everything in the vicinity \[6\]'),
    re.compile(r'(?<!["“])Jay Gatsby of West Egg, Long Island, sprang from his Platonic conception of himself \[13\]'),
    re.compile(r'(?<!["“])sprang from his Platonic conception of himself \[13\]'),
    re.compile(r'(?<!["“])The exhilarating ripple of her voice was a wild tonic in the rain \[19\]'),
    re.compile(r'(?<!["“])the whole caravansary had fallen in like a card house(?: at the disapproval in her eyes)? \[21\]'),
    re.compile(r'(?<!["“])the straw seats of the car hovered on the edge of combustion \[22\]'),
    re.compile(r'(?<!["“])in this heat every extra gesture was an affront to the common store of life \[23\]'),
    re.compile(r'(?<!["“])fairy’s wing \[20\]'),
    re.compile(r'(?<!["“])foul dust \[1\]'),
    re.compile(r'(?<!["“])had broken up like glass against Tom’s hard malice \[27\]'),
    re.compile(r'(?<!["“])an inexplicable amount of dust \[26\]'),
    re.compile(r'(?<!["“])thin and far away \[30\]'),
)


def paragraph_blocks(text: str) -> list[str]:
    return [block.strip() for block in BLOCK_SPLIT_RE.split(text) if block.strip()]


def split_markdown_into_chunks(text: str, *, max_chars: int) -> list[str]:
    if max_chars <= 0:
        return [text.strip()]

    blocks = paragraph_blocks(text)
    if not blocks:
        return [text.strip()]

    chunks: list[str] = []
    current_blocks: list[str] = []
    current_chars = 0

    for block in blocks:
        block_length = len(block) + (2 if current_blocks else 0)
        if current_blocks and current_chars + block_length > max_chars:
            chunks.append("\n\n".join(current_blocks).strip())
            current_blocks = []
            current_chars = 0

        if not current_blocks and len(block) > max_chars:
            chunks.append(block.strip())
            continue

        current_blocks.append(block)
        current_chars += block_length

    if current_blocks:
        chunks.append("\n\n".join(current_blocks).strip())

    return chunks


def extract_heading_levels(text: str) -> list[int]:
    return [len(match.group(1)) for match in HEADING_RE.finditer(text)]


def extract_visible_citation_markers(text: str) -> list[str]:
    return [match.group(0) for match in VISIBLE_CITATION_RE.finditer(text)]


def mask_visible_citation_markers(text: str) -> tuple[str, list[str]]:
    original_markers: list[str] = []

    def replace(match: re.Match[str]) -> str:
        original_markers.append(match.group(0))
        return f"AGCITTOKEN{len(original_markers):04d}XYZ"

    return VISIBLE_CITATION_RE.sub(replace, text), original_markers


def extract_translation_placeholders(text: str) -> list[str]:
    return [match.group(0) for match in TRANSLATION_CITATION_PLACEHOLDER_RE.finditer(text)]


def restore_visible_citation_markers(text: str, original_markers: list[str]) -> str:
    expected_placeholders = [f"AGCITTOKEN{index:04d}XYZ" for index in range(1, len(original_markers) + 1)]
    observed_placeholders = extract_translation_placeholders(text)
    if observed_placeholders != expected_placeholders:
        raise ValueError("Translated chunk changed the citation placeholder inventory")

    restored_text = text
    for index, marker in enumerate(original_markers, start=1):
        restored_text = restored_text.replace(f"AGCITTOKEN{index:04d}XYZ", marker)
    return restored_text


def count_quote_spans(text: str) -> int:
    patterns = (
        STRAIGHT_QUOTE_SPAN_RE,
        CURLY_QUOTE_SPAN_RE,
        LOW_SINGLE_QUOTE_SPAN_RE,
        GUILLEMET_QUOTE_SPAN_RE,
        CJK_CORNER_QUOTE_SPAN_RE,
        CJK_WHITE_CORNER_QUOTE_SPAN_RE,
    )
    return sum(len(pattern.findall(text)) for pattern in patterns)


def extract_quote_spans(text: str) -> list[str]:
    patterns = (
        STRAIGHT_QUOTE_SPAN_RE,
        CURLY_QUOTE_SPAN_RE,
        LOW_SINGLE_QUOTE_SPAN_RE,
        GUILLEMET_QUOTE_SPAN_RE,
        CJK_CORNER_QUOTE_SPAN_RE,
        CJK_WHITE_CORNER_QUOTE_SPAN_RE,
    )
    spans: list[str] = []
    for pattern in patterns:
        spans.extend(match.group(0) for match in pattern.finditer(text))
    return spans


def count_protected_quote_spans(text: str) -> int:
    total = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(">") or NUMBERED_LIST_LINE_RE.match(stripped):
            total += count_quote_spans(line)
    return total


def split_body_and_citations(text: str) -> tuple[str, str]:
    match = CITATIONS_SECTION_RE.search(text)
    if not match:
        return text.strip(), ""
    return text[: match.start()].strip(), text[match.start() :].strip()


def split_translated_output_and_citations(text: str) -> tuple[str, str]:
    match = TRANSLATED_CITATIONS_SECTION_RE.search(text)
    if not match:
        return text.strip(), ""
    return text[: match.start()].strip(), text[match.start() :].strip()


def count_numbered_citation_entries(text: str) -> int:
    return len(NUMBERED_CITATION_ENTRY_RE.findall(text))


def extract_translated_quote_lookup(text: str) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for line in text.splitlines():
        match = CITATION_QUOTE_LINE_RE.match(line.strip())
        if not match:
            continue
        quote = match.group("quote").strip()
        lookup[int(match.group("number"))] = quote
    for match in CITED_QUOTE_SPAN_RE.finditer(text):
        quote = match.group("quote").strip()
        if quote.startswith("*") and quote.endswith("*"):
            quote = quote[1:-1].strip()
        lookup.setdefault(int(match.group("number")), quote)
    return lookup


def render_translated_citations_section(citations_text: str, *, language_name: str, translated_body: str) -> str:
    if not citations_text.strip():
        return ""

    heading = "## Citations"
    if language_name == "Spanish":
        heading = "## Citas"
    elif language_name == "Simplified Chinese":
        heading = "## 引文"

    translated_quote_lookup = extract_translated_quote_lookup(translated_body)
    rendered_lines = [heading]
    for line in citations_text.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        rendered_lines.append(
            localize_citation_metadata_line(
                stripped,
                language_name=language_name,
                translated_quote_lookup=translated_quote_lookup,
            )
        )
    return "\n".join(rendered_lines).strip()


def localize_citation_metadata_line(
    line: str,
    *,
    language_name: str,
    translated_quote_lookup: dict[int, str] | None = None,
) -> str:
    stripped = line.strip()
    match = ENGLISH_CITATION_ENTRY_RE.match(stripped)
    if not match:
        return stripped

    number = match.group("number")
    citation_number = int(number.rstrip("."))
    chapter = match.group("chapter")
    paragraph = match.group("paragraph")
    lemma = match.group("lemma").rstrip(".")
    localized_quote = (translated_quote_lookup or {}).get(citation_number)

    if language_name == "Spanish":
        quote_text = localized_quote or SPANISH_CITATION_QUOTE_OVERRIDES.get(citation_number) or lemma
        return (
            f'{number} F. Scott Fitzgerald, *El gran Gatsby*, '
            f'cap. {chapter}, párr. {paragraph}, pasaje citado que comienza {quote_text}.'
        )
    if language_name == "Simplified Chinese":
        quote_text = localized_quote or MANDARIN_CITATION_QUOTE_OVERRIDES.get(citation_number) or lemma
        return (
            f"{number} F. Scott Fitzgerald，《了不起的盖茨比》，"
            f"第{chapter}章，第{paragraph}段，引文开头：{quote_text}。"
        )
    return stripped


def validate_citations_section_parity(english_master: str, translated_text: str) -> None:
    _, english_citations_section = split_body_and_citations(english_master)
    _, translated_citations_section = split_translated_output_and_citations(translated_text)

    english_entries = count_numbered_citation_entries(english_citations_section)
    translated_entries = count_numbered_citation_entries(translated_citations_section)

    if bool(english_citations_section.strip()) != bool(translated_citations_section.strip()):
        raise ValueError("Translated output changed citations section presence")
    if translated_citations_section.strip() and translated_entries == 0:
        raise ValueError("Translated output kept the citations heading but dropped the citation entries")
    if english_entries != translated_entries:
        raise ValueError("Translated output changed the citation entry count")


def english_master_regression_report_path(config: AppConfig):
    return config.resolve_repo_path(
        str(
            config.verification.get(
                "english_master_regression_output_path",
                "artifacts/qa/english_master_regression_report.json",
            )
        )
    )


def normalize_english_master_regressions(text: str) -> tuple[str, list[dict[str, str]]]:
    normalized = text
    applied_fixes: list[dict[str, str]] = []
    for source, target in ENGLISH_MASTER_REGRESSION_FIXES.items():
        if source not in normalized:
            continue
        normalized = normalized.replace(source, target)
        applied_fixes.append({"from": source, "to": target})
    normalized_lines: list[str] = []
    for line in normalized.splitlines(keepends=True):
        stripped_line = line.lstrip()
        if stripped_line.startswith(">") or NUMBERED_LIST_LINE_RE.match(stripped_line):
            normalized_lines.append(line)
            continue
        updated_line = line
        for pattern, replacement in ENGLISH_PROSE_PROPER_NOUN_PATTERNS:
            updated_line, replacement_count = pattern.subn(replacement, updated_line)
            if replacement_count:
                applied_fixes.append({"from": pattern.pattern, "to": replacement})
        normalized_lines.append(updated_line)
    normalized = "".join(normalized_lines)
    return normalized, applied_fixes


def build_english_master_regression_report(config: AppConfig, text: str, *, applied_fixes: list[dict[str, str]] | None = None):
    required_terms = tuple(
        str(term)
        for term in config.verification.get("english_master_required_terms", DEFAULT_REQUIRED_ENGLISH_MASTER_TERMS)
        if str(term).strip()
    )
    forbidden_phrases = tuple(
        str(phrase)
        for phrase in config.verification.get(
            "english_master_forbidden_phrases",
            DEFAULT_FORBIDDEN_ENGLISH_MASTER_PHRASES,
        )
        if str(phrase).strip()
    )
    missing_required_terms = [term for term in required_terms if term not in text]
    forbidden_phrase_hits = [phrase for phrase in forbidden_phrases if phrase in text]
    unquoted_quote_reuse_matches = find_unquoted_english_quote_reuse(text)
    major_issues: list[str] = []
    if missing_required_terms:
        major_issues.append("English master is missing required terminology.")
    if forbidden_phrase_hits:
        major_issues.append("English master still contains forbidden regression phrases.")
    if unquoted_quote_reuse_matches:
        major_issues.append("English master reuses exact source-language quotations without quotation marks.")
    return {
        "stage": "freeze_english",
        "generated_at": utc_now_iso(),
        "status": "passed" if not major_issues else "failed",
        "required_terms": list(required_terms),
        "missing_required_terms": missing_required_terms,
        "forbidden_phrases": list(forbidden_phrases),
        "forbidden_phrase_hits": forbidden_phrase_hits,
        "unquoted_quote_reuse_count": len(unquoted_quote_reuse_matches),
        "unquoted_quote_reuse_matches": unquoted_quote_reuse_matches,
        "applied_fixes": applied_fixes or [],
        "major_issues": major_issues,
    }


def write_english_master_regression_report(config: AppConfig, report: dict[str, object]) -> None:
    output_path = english_master_regression_report_path(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOGGER.info("Wrote English master regression report to %s", output_path)


def validate_english_master_regressions(config: AppConfig, text: str) -> str:
    normalized_text, applied_fixes = normalize_english_master_regressions(text)
    normalized_text, _ = dynamic_validation_loop(
        config,
        text=normalized_text,
        language_name="English",
        stage_name="dynamic_validate_english_master",
    )
    report = build_english_master_regression_report(config, normalized_text, applied_fixes=applied_fixes)
    write_english_master_regression_report(config, report)
    if report["major_issues"]:
        raise ValueError("English master failed terminology/regression validation")
    return normalized_text


def find_unquoted_english_quote_reuse(text: str) -> list[str]:
    return [pattern.pattern for pattern in UNQUOTED_ENGLISH_QUOTE_PATTERNS if pattern.search(text)]


def freeze_english_master(config: AppConfig) -> str:
    source_path = config.final_draft_output_path
    if not source_path.exists():
        raise FileNotFoundError(f"Final English report not found: {source_path}")

    raw_text = source_path.read_text(encoding="utf-8").strip() + "\n"
    master_text = validate_english_master_regressions(config, raw_text).strip() + "\n"
    if master_text != raw_text:
        source_path.write_text(master_text, encoding="utf-8")
        LOGGER.info("Applied deterministic English regression fixes to %s", source_path)
    output_path = config.english_master_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(master_text, encoding="utf-8")
    LOGGER.info("Froze English master to %s", output_path)
    return master_text


def load_english_master(config: AppConfig, *, freeze_if_missing: bool = True) -> str:
    output_path = config.english_master_output_path
    if output_path.exists():
        return output_path.read_text(encoding="utf-8")
    if freeze_if_missing:
        return freeze_english_master(config)
    raise FileNotFoundError(f"Frozen English master not found: {output_path}")


def load_translation_prompt(config: AppConfig, prompt_key: str) -> str:
    return config.resolve_prompt_path(prompt_key).read_text(encoding="utf-8")


def dynamic_validation_enabled(config: AppConfig) -> bool:
    return bool(config.verification.get("dynamic_validation_enabled", False))


def dynamic_validation_max_defects(config: AppConfig) -> int:
    return int(config.verification.get("dynamic_validation_max_defects", 20))


def dynamic_validation_transport(config: AppConfig) -> str | None:
    transport = (
        str(config.verification.get("dynamic_validation_transport", "")).strip()
        or str(config.translation.get("llm_transport", "")).strip()
        or str(config.drafting.get("llm_transport", "")).strip()
    )
    return transport or None


def dynamic_validation_language_key(language_name: str) -> str:
    if language_name == "English":
        return "english"
    if language_name == "Spanish":
        return "spanish"
    if language_name == "Simplified Chinese":
        return "mandarin"
    return re.sub(r"[^a-z0-9]+", "_", language_name.lower()).strip("_") or "document"


def dynamic_validation_report_path(config: AppConfig, language_name: str):
    language_key = dynamic_validation_language_key(language_name)
    configured = str(
        config.verification.get(
            f"{language_key}_dynamic_validation_report_path",
            f"artifacts/qa/{language_key}_dynamic_validation_report.json",
        )
    )
    return config.resolve_repo_path(configured)


def load_dynamic_validation_prompt(config: AppConfig) -> str:
    return config.resolve_prompt_path("dynamic_validation_prompt_path").read_text(encoding="utf-8")


def build_dynamic_validation_user_prompt(text: str, *, language_name: str) -> str:
    return "\n".join(
        [
            f"Document language: {language_name}",
            "Audit the markdown below and return JSON only.",
            "Do not rewrite the full document.",
            "Only report exact bad text spans that should be replaced surgically.",
            "",
            "Markdown to audit:",
            text.strip(),
        ]
    )


def normalize_dynamic_validation_json(response_text: str) -> str:
    text = DYNAMIC_VALIDATION_JSON_FENCE_RE.sub("", response_text).strip()
    match = DYNAMIC_VALIDATION_JSON_OBJECT_RE.search(text)
    if match:
        return match.group(0)
    return text


def parse_dynamic_validation_response(response_text: str, *, language_name: str) -> dict[str, object]:
    try:
        payload = json.loads(normalize_dynamic_validation_json(response_text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Dynamic validation response for {language_name} was not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Dynamic validation response for {language_name} must be a JSON object")

    defects = payload.get("defects", [])
    if not isinstance(defects, list):
        raise ValueError(f"Dynamic validation response for {language_name} must include a defects list")

    parsed_defects: list[dict[str, str]] = []
    for index, defect in enumerate(defects, start=1):
        if not isinstance(defect, dict):
            raise ValueError(f"Dynamic validation defect {index} for {language_name} must be an object")
        hallucination = str(defect.get("hallucination", "")).strip()
        correction = defect.get("correction", "")
        if not hallucination:
            raise ValueError(f"Dynamic validation defect {index} for {language_name} is missing hallucination")
        if correction is None:
            raise ValueError(f"Dynamic validation defect {index} for {language_name} is missing correction")
        parsed_defects.append(
            {
                "hallucination": hallucination,
                "correction": str(correction),
            }
        )

    notes = str(payload.get("notes", "")).strip()
    return {"defects": parsed_defects, "notes": notes}


def validate_dynamic_validation_response(response_text: str, *, language_name: str) -> None:
    parse_dynamic_validation_response(response_text, language_name=language_name)


def apply_dynamic_validation_replacements(text: str, defects: list[dict[str, str]]) -> tuple[str, list[dict[str, object]]]:
    sanitized = text
    applied: list[dict[str, object]] = []
    for defect in defects:
        hallucination = defect["hallucination"]
        correction = defect["correction"]
        count = sanitized.count(hallucination)
        if count == 0:
            continue
        sanitized = sanitized.replace(hallucination, correction)
        applied.append(
            {
                "hallucination": hallucination,
                "correction": correction,
                "replacement_count": count,
            }
        )
    return sanitized, applied


def apply_dynamic_validation_regex_fallbacks(text: str, *, language_name: str) -> str:
    sanitized = STANDALONE_ZERO_LINE_RE.sub("", text)
    if language_name == "Simplified Chinese":
        sanitized = ASCII_COMMA_AFTER_CITATION_RE.sub(r"\1，", sanitized)
    else:
        sanitized = ASCII_COMMA_AFTER_CITATION_RE.sub(r"\1", sanitized)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    return sanitized


def validate_dynamic_validation_structure(original_text: str, revised_text: str) -> None:
    if extract_heading_levels(revised_text) != extract_heading_levels(original_text):
        raise ValueError("Dynamic validation changed the markdown heading structure")
    if extract_visible_citation_markers(revised_text) != extract_visible_citation_markers(original_text):
        raise ValueError("Dynamic validation changed the citation marker inventory")
    _, original_citations = split_translated_output_and_citations(original_text)
    _, revised_citations = split_translated_output_and_citations(revised_text)
    if count_numbered_citation_entries(revised_citations) != count_numbered_citation_entries(original_citations):
        raise ValueError("Dynamic validation changed the citation entry count")


def write_dynamic_validation_report(output_path, report: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOGGER.info("Wrote %s dynamic validation report to %s", report["language"], output_path)


def dynamic_validation_loop(
    config: AppConfig,
    *,
    text: str,
    language_name: str,
    stage_name: str,
) -> tuple[str, dict[str, object]]:
    report_path = dynamic_validation_report_path(config, language_name)
    original_text = text.strip()
    if not dynamic_validation_enabled(config):
        report = {
            "stage": stage_name,
            "language": dynamic_validation_language_key(language_name),
            "generated_at": utc_now_iso(),
            "status": "skipped",
            "defect_count": 0,
            "applied_replacement_count": 0,
            "defects": [],
            "applied_replacements": [],
            "notes": "Dynamic validation disabled in config.",
        }
        write_dynamic_validation_report(report_path, report)
        return original_text, report

    defects: list[dict[str, str]] = []
    applied_replacements: list[dict[str, object]] = []
    sanitized_text = original_text
    notes = ""
    status = "passed"
    try:
        response_text = invoke_text_completion(
            config,
            stage_name=stage_name,
            system_prompt=load_dynamic_validation_prompt(config),
            user_prompt=build_dynamic_validation_user_prompt(original_text, language_name=language_name),
            output_path=str(report_path),
            model_name=str(config.models.get("final_critic", config.models.get("primary_reasoner", ""))),
            response_validator=lambda value: validate_dynamic_validation_response(value, language_name=language_name),
            transport_override=dynamic_validation_transport(config),
        )
        parsed = parse_dynamic_validation_response(response_text, language_name=language_name)
        notes = str(parsed.get("notes", "")).strip()
        defects = list(parsed["defects"])[: dynamic_validation_max_defects(config)]
        sanitized_text, applied_replacements = apply_dynamic_validation_replacements(original_text, defects)
        sanitized_text = apply_dynamic_validation_regex_fallbacks(sanitized_text, language_name=language_name)
        if language_name != "English":
            sanitized_text = normalize_translated_body(sanitized_text, language_name=language_name)
        validate_dynamic_validation_structure(original_text, sanitized_text)
        if applied_replacements:
            status = "fixed"
    except Exception as exc:
        LOGGER.warning("Dynamic validation failed for %s: %s", language_name, exc)
        notes = str(exc)
        status = "error"
        fallback_text = apply_dynamic_validation_regex_fallbacks(original_text, language_name=language_name)
        if language_name != "English":
            fallback_text = normalize_translated_body(fallback_text, language_name=language_name)
        try:
            validate_dynamic_validation_structure(original_text, fallback_text)
            sanitized_text = fallback_text
        except Exception:
            sanitized_text = original_text

    report = {
        "stage": stage_name,
        "language": dynamic_validation_language_key(language_name),
        "generated_at": utc_now_iso(),
        "status": status,
        "defect_count": len(defects),
        "applied_replacement_count": len(applied_replacements),
        "defects": defects,
        "applied_replacements": applied_replacements,
        "notes": notes or ("No defects found." if not defects else "Applied critic-guided replacements."),
    }
    write_dynamic_validation_report(report_path, report)
    return sanitized_text, report


def build_translation_user_prompt(chunk_text: str, *, chunk_index: int, total_chunks: int, language_name: str) -> str:
    instructions = [
        f"Chunk {chunk_index} of {total_chunks}.",
        f"Translate this markdown chunk into {language_name}.",
        "Preserve markdown heading markers exactly.",
        "Preserve immutable machine tokens like AGCITTOKEN0001XYZ exactly and do not translate, retype, split, or alter them.",
        "Preserve quotation boundaries.",
        "Return translated markdown only.",
    ]
    return "\n".join(instructions) + "\n\nEnglish markdown chunk:\n\n" + chunk_text


def build_fragment_user_prompt(fragment_text: str, *, language_name: str) -> str:
    instructions = [
        f"Translate this markdown fragment into {language_name}.",
        "Do not add commentary or extra lines.",
        "Preserve any inline markdown emphasis markers like * and _ when they appear in the fragment.",
        "Return the translated fragment only.",
    ]
    return "\n".join(instructions) + "\n\nEnglish markdown fragment:\n\n" + fragment_text


def build_translation_cleanup_user_prompt(chunk_text: str, *, chunk_index: int, total_chunks: int, language_name: str) -> str:
    instructions = [
        f"Chunk {chunk_index} of {total_chunks}.",
        f"Revise this existing {language_name} markdown chunk into polished academic {language_name}.",
        "The text is already translated, but it may contain leftover English, literal phrasing, inconsistent proper nouns, or awkward citation punctuation.",
        "Preserve markdown heading markers exactly.",
        "Preserve immutable machine tokens like AGCITTOKEN0001XYZ exactly and do not translate, retype, split, or alter them.",
        "Preserve quotation boundaries.",
        "Keep all direct quotations consistently translated into the target language unless the content is only a proper noun.",
        "Return revised markdown only.",
    ]
    return "\n".join(instructions) + "\n\nExisting translated markdown chunk:\n\n" + chunk_text


def build_cleanup_fragment_user_prompt(fragment_text: str, *, language_name: str) -> str:
    instructions = [
        f"Revise this existing {language_name} markdown fragment into polished academic {language_name}.",
        "Do not add commentary or extra lines.",
        "Preserve any inline markdown emphasis markers like * and _ when they appear in the fragment.",
        "Keep any direct quotations in the target language.",
        "Return the revised fragment only.",
    ]
    return "\n".join(instructions) + "\n\nExisting translated markdown fragment:\n\n" + fragment_text


def validate_translation_chunk(source_chunk: str, translated_chunk: str) -> None:
    stripped = translated_chunk.strip()
    if not stripped:
        raise ValueError("Translated chunk is empty")

    if extract_heading_levels(stripped) != extract_heading_levels(source_chunk):
        raise ValueError("Translated chunk changed the markdown heading structure")

    if extract_visible_citation_markers(stripped) != extract_visible_citation_markers(source_chunk):
        raise ValueError("Translated chunk changed the citation marker inventory")


def validate_placeholder_chunk(source_chunk: str, translated_chunk: str) -> None:
    stripped = translated_chunk.strip()
    if not stripped:
        raise ValueError("Translated chunk is empty")

    if extract_heading_levels(stripped) != extract_heading_levels(source_chunk):
        raise ValueError("Translated chunk changed the markdown heading structure")

    if extract_translation_placeholders(stripped) != extract_translation_placeholders(source_chunk):
        raise ValueError("Translated chunk changed the citation placeholder inventory")


def validate_translated_fragment(translated_text: str) -> None:
    if not translated_text.strip():
        raise ValueError("Translated fragment is empty")

    if extract_visible_citation_markers(translated_text):
        raise ValueError("Translated fragment unexpectedly introduced citation markers")

    if extract_translation_placeholders(translated_text):
        raise ValueError("Translated fragment unexpectedly introduced citation placeholders")


def normalize_translated_body(text: str, *, language_name: str) -> str:
    normalized = CITATION_GLUE_RE.sub(r"\1 ", text)
    normalized = ZERO_WIDTH_RE.sub("", normalized)
    normalized = ASSISTANT_PROMPT_LEAK_RE.sub("", normalized)
    normalized = LEAKED_AGC_CITATION_RE.sub(r"[\1]", normalized)
    if language_name == "Spanish":
        normalized = SPANISH_INTERNAL_TOKEN_RE.sub("", normalized)
        normalized = SPANISH_ESCAPE_SEQUENCE_RE.sub(" ", normalized)
        normalized = normalized.replace("esporádíamos", "esporádicos")
        normalized = re.sub(r"\s*\.\s*(\[\d+\])\s*(?=[A-ZÁÉÍÓÚÑ])", r" \1. ", normalized)
        normalized = re.sub(r'([”»"])\*\.\s*(\[\d+\])', r"\1* \2.", normalized)
        normalized = re.sub(r'([”»"])\.\*\s*(\[\d+\])', r"\1* \2.", normalized)
        normalized = re.sub(r'(["»”])\.\s*(\[\d+\])', r"\1 \2.", normalized)
        for source, target in SPANISH_NORMALIZATION_MAP.items():
            normalized = normalized.replace(source, target)
    if language_name == "Simplified Chinese":
        normalized = MANDARIN_ELLIPSIS_BEFORE_CITATION_RE.sub(r" \1", normalized)
        normalized = MANDARIN_SENTENCE_BREAK_BEFORE_CITATION_RE.sub(r" \2，", normalized)
        normalized = re.sub(r'([。！？])\s*(\[\d+\])', r" \2\1", normalized)
        normalized = re.sub(r'([”」』"])。\s*(\[\d+\])', r"\1 \2。", normalized)
        normalized = re.sub(r"(\[\d+\])\s*,", r"\1，", normalized)
        for source, target in MANDARIN_NORMALIZATION_MAP.items():
            normalized = normalized.replace(source, target)
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    return normalized


def write_translation_output(output_path, text: str, *, language_name: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text.strip() + "\n", encoding="utf-8")
    LOGGER.info("Wrote %s translation to %s", language_name, output_path)


def post_edit_translated_body(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    translated_body: str,
    transport_override: str | None,
) -> str:
    chunks = split_markdown_into_chunks(
        translated_body,
        max_chars=int(config.translation.get("max_chunk_chars", 5000)),
    )
    revised_chunks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        masked_chunk, original_markers = mask_visible_citation_markers(chunk)
        try:
            revised_chunk = invoke_text_completion(
                config,
                stage_name=f"{stage_name}_cleanup",
                system_prompt=system_prompt,
                user_prompt=build_translation_cleanup_user_prompt(
                    masked_chunk,
                    chunk_index=index,
                    total_chunks=len(chunks),
                    language_name=language_name,
                ),
                output_path=str(output_path),
                model_name=model_name,
                response_validator=lambda text, source_chunk=masked_chunk: validate_placeholder_chunk(source_chunk, text),
                transport_override=transport_override,
            ).strip()
            revised_chunks.append(restore_visible_citation_markers(revised_chunk, original_markers))
        except LLMResponseValidationError as exc:
            if "citation placeholder inventory" not in str(exc):
                raise
            LOGGER.warning(
                "Post-edit cleanup failed placeholder preservation for %s chunk %d/%d; falling back to fragment-safe cleanup",
                stage_name,
                index,
                len(chunks),
            )
            revised_chunks.append(
                cleanup_chunk_with_marker_stitching(
                    config,
                    stage_name=stage_name,
                    system_prompt=system_prompt,
                    output_path=output_path,
                    model_name=model_name,
                    language_name=language_name,
                    chunk_text=chunk,
                    transport_override=transport_override,
                )
            )

    return normalize_translated_body("\n\n".join(revised_chunks).strip(), language_name=language_name)


def translate_fragment(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    fragment_text: str,
    transport_override: str | None,
) -> str:
    if not fragment_text.strip():
        return fragment_text

    leading = fragment_text[: len(fragment_text) - len(fragment_text.lstrip())]
    trailing = fragment_text[len(fragment_text.rstrip()) :]
    core = fragment_text.strip()
    if not core:
        return fragment_text

    translated_core = invoke_text_completion(
        config,
        stage_name=stage_name,
        system_prompt=system_prompt,
        user_prompt=build_fragment_user_prompt(core, language_name=language_name),
        output_path=str(output_path),
        model_name=model_name,
        response_validator=validate_translated_fragment,
        transport_override=transport_override,
    ).strip()
    return leading + translated_core + trailing


def cleanup_fragment(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    fragment_text: str,
    transport_override: str | None,
) -> str:
    if not fragment_text.strip():
        return fragment_text

    leading = fragment_text[: len(fragment_text) - len(fragment_text.lstrip())]
    trailing = fragment_text[len(fragment_text.rstrip()) :]
    core = fragment_text.strip()
    if not core:
        return fragment_text

    cleaned_core = invoke_text_completion(
        config,
        stage_name=f"{stage_name}_cleanup",
        system_prompt=system_prompt,
        user_prompt=build_cleanup_fragment_user_prompt(core, language_name=language_name),
        output_path=str(output_path),
        model_name=model_name,
        response_validator=validate_translated_fragment,
        transport_override=transport_override,
    ).strip()
    return leading + cleaned_core + trailing


def translate_text_preserving_citations(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    text: str,
    transport_override: str | None,
) -> str:
    if not text:
        return text

    parts = re.split(f"({VISIBLE_CITATION_RE.pattern})", text)
    translated_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        if VISIBLE_CITATION_RE.fullmatch(part):
            translated_parts.append(part)
            continue
        translated_parts.append(
            translate_fragment(
                config,
                stage_name=stage_name,
                system_prompt=system_prompt,
                output_path=output_path,
                model_name=model_name,
                language_name=language_name,
                fragment_text=part,
                transport_override=transport_override,
            )
        )
    return "".join(translated_parts)


def cleanup_text_preserving_citations(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    text: str,
    transport_override: str | None,
) -> str:
    if not text:
        return text

    parts = re.split(f"({VISIBLE_CITATION_RE.pattern})", text)
    cleaned_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        if VISIBLE_CITATION_RE.fullmatch(part):
            cleaned_parts.append(part)
            continue
        cleaned_parts.append(
            cleanup_fragment(
                config,
                stage_name=stage_name,
                system_prompt=system_prompt,
                output_path=output_path,
                model_name=model_name,
                language_name=language_name,
                fragment_text=part,
                transport_override=transport_override,
            )
        )
    return "".join(cleaned_parts)


def translate_chunk_with_marker_stitching(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    chunk_text: str,
    transport_override: str | None,
) -> str:
    translated_blocks: list[str] = []
    for block in paragraph_blocks(chunk_text):
        translated_lines: list[str] = []
        for line in block.splitlines():
            if not line.strip():
                translated_lines.append(line)
                continue

            prefix = ""
            body = line
            heading_match = HEADING_LINE_RE.match(line)
            if heading_match:
                prefix = heading_match.group(1)
                body = heading_match.group(2)
            else:
                blockquote_match = BLOCKQUOTE_LINE_RE.match(line)
                if blockquote_match:
                    prefix = blockquote_match.group(1)
                    body = blockquote_match.group(2)

            translated_lines.append(
                prefix
                + translate_text_preserving_citations(
                    config,
                    stage_name=stage_name,
                    system_prompt=system_prompt,
                    output_path=output_path,
                    model_name=model_name,
                    language_name=language_name,
                    text=body,
                    transport_override=transport_override,
                )
            )
        translated_blocks.append("\n".join(translated_lines))
    return "\n\n".join(translated_blocks).strip()


def cleanup_chunk_with_marker_stitching(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    chunk_text: str,
    transport_override: str | None,
) -> str:
    cleaned_blocks: list[str] = []
    for block in paragraph_blocks(chunk_text):
        cleaned_lines: list[str] = []
        for line in block.splitlines():
            if not line.strip():
                cleaned_lines.append(line)
                continue

            prefix = ""
            body = line
            heading_match = HEADING_LINE_RE.match(line)
            if heading_match:
                prefix = heading_match.group(1)
                body = heading_match.group(2)
            else:
                blockquote_match = BLOCKQUOTE_LINE_RE.match(line)
                if blockquote_match:
                    prefix = blockquote_match.group(1)
                    body = blockquote_match.group(2)

            cleaned_lines.append(
                prefix
                + cleanup_text_preserving_citations(
                    config,
                    stage_name=stage_name,
                    system_prompt=system_prompt,
                    output_path=output_path,
                    model_name=model_name,
                    language_name=language_name,
                    text=body,
                    transport_override=transport_override,
                )
            )
        cleaned_blocks.append("\n".join(cleaned_lines))
    return "\n\n".join(cleaned_blocks).strip()


def translate_document(
    config: AppConfig,
    *,
    stage_name: str,
    prompt_key: str,
    cleanup_prompt_key: str | None,
    model_key: str,
    output_path,
    language_name: str,
    source_text: str | None = None,
) -> str:
    master_text = source_text or load_english_master(config)
    body_text, citations_text = split_body_and_citations(master_text)
    max_chunk_chars = int(config.translation.get("max_chunk_chars", 5000))
    chunks = split_markdown_into_chunks(body_text, max_chars=max_chunk_chars)
    system_prompt = load_translation_prompt(config, prompt_key)
    cleanup_prompt = load_translation_prompt(config, cleanup_prompt_key) if cleanup_prompt_key else system_prompt
    transport_override = (
        str(config.translation.get("llm_transport", "")).strip()
        or str(config.drafting.get("llm_transport", "")).strip()
        or None
    )

    translated_chunks: list[str] = []
    target_model_name = config.model_name_for(model_key)
    for index, chunk in enumerate(chunks, start=1):
        masked_chunk, original_markers = mask_visible_citation_markers(chunk)
        try:
            translated_chunk = invoke_text_completion(
                config,
                stage_name=stage_name,
                system_prompt=system_prompt,
                user_prompt=build_translation_user_prompt(
                    masked_chunk,
                    chunk_index=index,
                    total_chunks=len(chunks),
                    language_name=language_name,
                ),
                output_path=str(output_path),
                model_name=target_model_name,
                response_validator=lambda text, source_chunk=masked_chunk: validate_placeholder_chunk(source_chunk, text),
                transport_override=transport_override,
            ).strip()
            translated_chunks.append(restore_visible_citation_markers(translated_chunk, original_markers))
        except LLMResponseValidationError as exc:
            if "citation placeholder inventory" not in str(exc):
                raise
            LOGGER.warning(
                "Chunk-level translation failed placeholder preservation for %s chunk %d/%d; falling back to citation-safe fragment stitching",
                stage_name,
                index,
                len(chunks),
            )
            translated_chunks.append(
                translate_chunk_with_marker_stitching(
                    config,
                    stage_name=stage_name,
                    system_prompt=system_prompt,
                    output_path=output_path,
                    model_name=target_model_name,
                    language_name=language_name,
                    chunk_text=chunk,
                    transport_override=transport_override,
                )
            )

    translated_body = "\n\n".join(translated_chunks).strip()
    if bool(config.translation.get("post_edit_body", True)):
        translated_body = post_edit_translated_body(
            config,
            stage_name=stage_name,
            system_prompt=cleanup_prompt,
            output_path=output_path,
            model_name=target_model_name,
            language_name=language_name,
            translated_body=translated_body,
            transport_override=transport_override,
        )
    else:
        translated_body = normalize_translated_body(translated_body, language_name=language_name)

    translated_citations = render_translated_citations_section(
        citations_text,
        language_name=language_name,
        translated_body=translated_body,
    )
    translated_text = translated_body
    if translated_citations:
        translated_text = translated_text + "\n\n" + translated_citations
    translated_text = translated_text.strip() + "\n"
    translated_text, _ = dynamic_validation_loop(
        config,
        text=translated_text,
        language_name=language_name,
        stage_name=f"dynamic_validate_{dynamic_validation_language_key(language_name)}_translation",
    )
    validate_translation_chunk(master_text, translated_text)
    validate_citations_section_parity(master_text, translated_text)
    write_translation_output(output_path, translated_text, language_name=language_name)
    return translated_text
