"""XWB protocol types, message construction, encoding, and cipher.

This module contains:
- Enumerations: ``ParamType``, ``SessionState``, ``CredentialSource``
- Data classes: ``RPCParameter``, ``RPCResponse``
- Factory functions: ``literal()``, ``list_param()``
- Encoding primitives: ``spack()``, ``lpack()``
- Cipher: ``encrypt()``, ``decrypt()``
- Message builders: ``build_connect_message()``,
  ``build_rpc_message()``, ``build_disconnect_message()``
- Response parser: ``parse_response()``
"""

from __future__ import annotations

import enum
import re as _re
from dataclasses import dataclass, field
from random import randint

from vista_test.rpc.errors import RPCError

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ParamType(enum.Enum):
    """RPC parameter types supported by the XWB protocol."""

    LITERAL = 0
    LIST = 2


class SessionState(enum.Enum):
    """States in the broker session state machine."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    HANDSHAKED = "handshaked"
    AUTHENTICATED = "authenticated"
    CONTEXT_SET = "context_set"


class CredentialSource(enum.Enum):
    """How credentials were obtained (internal use)."""

    EXPLICIT = "explicit"
    ENVIRONMENT = "environment"
    DEFAULT = "default"


class CipherType(enum.Enum):
    """Cipher table variant used by the VistA server.

    TRADITIONAL is the original table shipped with VistA/Kernel (XUSRB1.m).
    OSEHRA is the modified table used by some OSEHRA-derived systems.

    See: https://www.osehra.org/blog/vista-m-and-delphi-guis-problem
    """

    TRADITIONAL = "traditional"
    OSEHRA = "osehra"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RPCParameter:
    """A typed parameter for an RPC invocation.

    Attributes:
        param_type: LITERAL or LIST.
        value: String value (for LITERAL type).
        entries: Key-value pairs (for LIST type).
    """

    param_type: ParamType
    value: str = ""
    entries: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RPCResponse:
    """Parsed response from an RPC call.

    Attributes:
        raw: The raw response string from the server.
        value: Single value (for SINGLE VALUE responses), or None.
        lines: List of values (for ARRAY responses), or None.
    """

    raw: str
    value: str | None = None
    lines: list[str] | None = None

    @property
    def is_array(self) -> bool:
        """Whether this response contains multiple values."""
        return self.lines is not None


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def literal(value: str) -> RPCParameter:
    """Create a literal (string) parameter.

    Args:
        value: The string value to pass.

    Returns:
        RPCParameter with type LITERAL.
    """
    return RPCParameter(param_type=ParamType.LITERAL, value=value)


def list_param(entries: dict[str, str]) -> RPCParameter:
    """Create a list (key-value array) parameter.

    A list parameter must be the last parameter in the RPC's
    parameter list per the XWB protocol specification.

    Args:
        entries: Dictionary of string keys to string values.

    Returns:
        RPCParameter with type LIST.

    Raises:
        ValueError: If entries is empty.
    """
    if not entries:
        raise ValueError("list_param entries must not be empty")
    return RPCParameter(param_type=ParamType.LIST, entries=dict(entries))


# ---------------------------------------------------------------------------
# Encoding primitives
# ---------------------------------------------------------------------------


def spack(value: str) -> str:
    """S-PACK (Short Pack) encoding: ``chr(len) + value``.

    Args:
        value: String to encode. Maximum 255 characters.

    Returns:
        S-PACK encoded string.

    Raises:
        ValueError: If value exceeds 255 characters.
    """
    if len(value) > 255:
        raise ValueError(f"spack value exceeds 255 chars: {len(value)}")
    return chr(len(value)) + value


def lpack(value: str) -> str:
    """L-PACK (Length Pack) encoding with dynamic width.

    Uses 3-digit zero-padded length for values <= 999 characters
    and 5-digit zero-padded length for values > 999 characters
    (per XWB*1.1*65).

    Args:
        value: String to encode.

    Returns:
        L-PACK encoded string.
    """
    length = len(value)
    if length > 999:
        return f"{length:05d}{value}"
    return f"{length:03d}{value}"


# ---------------------------------------------------------------------------
# Cipher Tables
# ---------------------------------------------------------------------------

# Traditional cipher table — original VistA/Kernel (XUSRB1.m).
# Used by standard VA VistA, WorldVistA VEHU, and most deployments.
CIPHER_TRADITIONAL: list[str] = [
    "wkEo-ZJt!dG)49K{nX1BS$vH<&:Myf*>Ae0jQW=;|#PsO`'%+rmb[gpqN,l6/hFC@DcUa ]z~R}\"V\\iIxu?872.(TYL5_3",
    "rKv`R;M/9BqAF%&tSs#Vh)dO1DZP> *fX'u[.4lY=-mg_ci802N7LTG<]!CWo:3?{+,5Q}(@jaExn$~p\\IyHwzU\"|k6Jeb",
    "\\pV(ZJk\"WQmCn!Y,y@1d+~8s?[lNMxgHEt=uw|X:qSLjAI*}6zoF{T3#;ca)/h5%`P4$r]G'9e2if_>UDKb7<v0&- RBO.",
    "depjt3g4W)qD0V~NJar\\B \"?OYhcu[<Ms%Z`RIL_6:]AX-zG.#}$@vk7/5x&*m;(yb2Fn+l'PwUof1K{9,|EQi>H=CT8S!",
    "NZW:1}K$byP;jk)7'`x90B|cq@iSsEnu,(l-hf.&Y_?J#R]+voQXU8mrV[!p4tg~OMez CAaGFD6H53%L/dT2<*>\"{\\wI=",
    "vCiJ<oZ9|phXVNn)m K`t/SI%]A5qOWe\\&?;jT~M!fz1l>[D_0xR32c*4.P\"G{r7}E8wUgyudF+6-:B=$(sY,LkbHa#'@Q",
    "hvMX,'4Ty;[a8/{6l~F_V\"}qLI\\!@x(D7bRmUH]W15J%N0BYPkrs&9:$)Zj>u|zwQ=ieC-oGA.#?tfdcO3gp`S+En K2*<",
    "jd!W5[];4'<C$/&x|rZ(k{>?ghBzIFN}fAK\"#`p_TqtD*1E37XGVs@0nmSe+Y6Qyo-aUu%i8c=H2vJ\\) R:MLb.9,wlO~P",
    "2ThtjEM+!=xXb)7,ZV{*ci3\"8@_l-HS69L>]\\AUF/Q%:qD?1~m(yvO0e'<#o$p4dnIzKP|`NrkaGg.ufCRB[; sJYwW}5&",
    "vB\\5/zl-9y:Pj|=(R'7QJI *&CTX\"p0]_3.idcuOefVU#omwNZ`$Fs?L+1Sk<,b)hM4A6[Y%aDrg@~KqEW8t>H};n!2xG{",
    "sFz0Bo@_HfnK>LR}qWXV+D6`Y28=4Cm~G/7-5A\\b9!a#rP.l&M$hc3ijQk;),TvUd<[:I\"u1'NZSOw]*gxtE{eJp|y (?%",
    "M@,D}|LJyGO8`$*ZqH .j>c~h<d=fimszv[#-53F!+a;NC'6T91IV?(0x&/{B)w\"]Q\\YUWprk4:ol%g2nE7teRKbAPuS_X",
    ".mjY#_0*H<B=Q+FML6]s;r2:e8R}[ic&KA 1w{)vV5d,$u\"~xD/Pg?IyfthO@CzWp%!`N4Z'3-(o|J9XUE7k\\TlqSb>anG",
    "xVa1']_GU<X`|\\NgM?LS9{\"jT%s$}y[nvtlefB2RKJW~(/cIDCPow4,>#zm+:5b@06O3Ap8=*7ZFY!H-uEQk; .q)i&rhd",
    "I]Jz7AG@QX.\"%3Lq>METUo{Pp_ |a6<0dYVSv8:b)~W9NK`(r'4fs&wim\\kReC2hg=HOj$1B*/nxt,;c#y+![?lFuZ-5D}",
    "Rr(Ge6F Hx>q$m&C%M~Tn,:\"o'tX/*yP.{lZ!YkiVhuw_<KE5a[;}W0gjsz3]@7cI2\\QN?f#4p|vb1OUBD9)=-LJA+d`S8",
    "I~k>y|m};d)-7DZ\"Fe/Y<B:xwojR,Vh]O0Sc[`$sg8GXE!1&Qrzp._W%TNK(=J 3i*2abuHA4C'?Mv\\Pq{n#56LftUl@9+",
    "~A*>9 WidFN,1KsmwQ)GJM{I4:C%}#Ep(?HB/r;t.&U8o|l['Lg\"2hRDyZ5`nbf]qjc0!zS-TkYO<_=76a\\X@$Pe3+xVvu",
    "yYgjf\"5VdHc#uA,W1i+v'6|@pr{n;DJ!8(btPGaQM.LT3oe?NB/&9>Z`-}02*%x<7lsqz4OS ~E$\\R]KI[:UwC_=h)kXmF",
    "5:iar.{YU7mBZR@-K|2 \"+~`M%8sq4JhPo<_X\\Sg3WC;Tuxz,fvEQ1p9=w}FAI&j/keD0c?)LN6OHV]lGy'$*>nd[(tb!#",
]

# OSEHRA cipher table — used by some OSEHRA-derived VistA systems.
# See: https://www.osehra.org/blog/vista-m-and-delphi-guis-problem
CIPHER_OSEHRA: list[str] = [
    "VEB_0|=f3Y}m<5i$`W>znGA7P:O%H69[2r)jKh@uo\\wMb*Da !+T?q4-JI#d;8ypUQ]g\"~'&Cc.LNt/kX,e{vl1FRZs(xS",
    "D/Jg><p]1W6Rtqr.QYo8TBEMK-aAIyO(xG7lPz;=d)N}2F!U ,e0~$fk\"j[m*3s5@XnZShv+`b'{u&_\\9%|wL4ic:V?H#C",
    "?lBUvZq\\fwk+u#:50`SOF9,dp&*G-M=;{8Ai6/N7]bQ1szC!(PxW_YV~)3Lm.EIXD2aT|hKj$rnR@[\"c g'<>t%4oJHy}e",
    "MH,t9K%TwA17-Bzy+XJU?<>4mo @=6:Ipfnx/Y}R8Q\\aN~{)VjEW;|Sq]rl[0uLFd`g5Z#e!3$b\"P_.si&G(2'Cvkc*ODh",
    "vMy>\"X?bSLCl)'jhzHJk.fVc6#*[0OuP@\\{,&r(`Es:K!7wi$5F; DoY=p%e<t}4TQA2_W9adR]gNBG1~nIZ+3x-Um|8q/",
    ":\"XczmHx;oA%+vR$Mtr CBTU_w<uEK5f,SW*d8OaFGh]j'{7-~Qp#yqP>09si|VY1J!/[lN23&L4`=.D6)ZIb\\n?}(ek@g",
    "j7Qh[YU.u6~xm<`vfe%_g-MRF(#iK=trl}C)>GEDN *$OdHzBA98aLJ|2WP:@ko0wy4I/S&,q']5!13XcVs\\?Zp\"+{;Tbn",
    "\\UVZ;.&]%7fGq`*SA=Kv/-Xr1OBHiwhP5ukYo{2\"}d |NsT,>!x6y~cz[C)pe8m9LaRI(MEFlt:Qg#D'n$W04b@_+?j<3J",
    "MgSvV\"U'dj5Yf6K*W)/:z$oi7GJ|t(1Ak=ZC,@]Q0?8DnbE[+L`{mq>;aOR}wcB4sF_e9rh2l\\x<. PyNpu%IT!&3#HX~-",
    "rFkn4Z0cH7)`6Xq|yL #wmuW?Gf!2YES;.B_D=el}hN[M&x(*AasU9otd+{]g>TQjp<:v%5O\"zI\\@$Rb~8i-3/'V1,CJPK",
    "\\'%u+W)mK41L#:A6!;7(\"tnyRlaOe09]3EFd ITf.`@P[Q{B$_iYhZo*kbc|HUgz=D>Svr8x,X~-<NsjM}C/&J?p2wV5qG",
    "QCl_329e+DTp&\\?jNys V]k*M\"X!$Y6[i@g>{RvF'01(45LJZU,:-uAwtB;7|%fx.n`IhSE<OoW~=bdP#/KHzrc)8mG}aq",
    "!{w*PR[B9Oli~T, rFc\"/?ast8=)-_Dgo<E#n4HYA%f'N;0@S7pJ`kGIedM|+C2yjvL5b3K6\\Z]V(.h}umxz>XQ$qUW:1&",
    "}:SHZ|O~A-bcyJ4%'5vM+ ;eo.$B)Vp\\,kTDz1sGL`]*=mg2nxYPd&lErN3[8qF0@u\"a_>wQKI{f6C7?9RX(t#i/U<j!Wh",
    ",ry*|7<1keO:Wi C/zh4IZ>x!F[_(\"Dbu%Hl5Pg=]QG.LKcJ0&ont@+{;ATX6jMwBv?2#f`q\\}VYm'8Es$NpU)dR~S9a3-",
    "h,=/:pJ$@mlY-`bwQ)e3Xt8.RUSMV 2A;j[PN}TE9x~kL&<ns5q>_#c1%K+rIuFoa(zyDWdH]?\\GB0g*4f6\"Z!'v{7|OiC",
    "/$*b.ts0vOx_-o\"l3MHI~}!E`eJimPd>Sn&wzFUh?Kf4)g5X<,8pD:9LA{a[k;'|GyYQ=R2B\\#q+cru6N1W@(C TV]7Z%j",
    "qEoC?YWNtV{Brg,I(i:e7Jd#6m!D8XT\"n[$~1*ZcxL.Kh2s4%Q&ju\\5Gvazw+9pF@k`HA)=U3/< -}'0b;|PfSRl_MO]y>",
    "`@X:!R[\\tY5OBcZPh$rM_a-\"vgJG%|}oIH)wWQ*jDVxlp,'+S zu(&7?>KCn4y1dE02q6b<;F=8]9NAmT{Li3f/esUk.~#",
    "\\Zr';/SMsG76Lj$aBc[#k>u=_O@2J&X{Aft xV4~vz8Q}q)0K.NIpRnYwDhg+<\"H-!(PF:m*]?,WCT|dE9o53%`liUey1b",
]

# Map CipherType enum to the corresponding table
_CIPHER_TABLES: dict[CipherType, list[str]] = {
    CipherType.TRADITIONAL: CIPHER_TRADITIONAL,
    CipherType.OSEHRA: CIPHER_OSEHRA,
}

# Default cipher type — Traditional is used by standard VA VistA / VEHU
DEFAULT_CIPHER = CipherType.TRADITIONAL


def encrypt(plaintext: str, cipher: CipherType = DEFAULT_CIPHER) -> str:
    """Encrypt a string using the specified cipher table.

    Picks two random row indices into the cipher table and performs
    substitution: find character position in row *ra*, replace with
    the character at the same position in row *rb*.  Matches the M
    server's ``$$ENCRYP^XUSRB1`` which uses ``$TR`` (transliterate).

    Args:
        plaintext: The string to encrypt.
        cipher: Which cipher table to use (default: TRADITIONAL).

    Returns:
        Encrypted string with row-index prefix/suffix characters.
    """
    table = _CIPHER_TABLES[cipher]
    ra = randint(0, 19)
    rb = randint(1, 19)
    while rb == ra:
        rb = randint(1, 19)
    row_a = table[ra]
    row_b = table[rb]
    result = chr(ra + 32)
    for ch in plaintext:
        idx = row_a.find(ch)
        if idx == -1:
            result += ch
        else:
            result += row_b[idx]
    result += chr(rb + 32)
    return result


def decrypt(ciphertext: str, cipher: CipherType = DEFAULT_CIPHER) -> str:
    """Decrypt a string encrypted with the specified cipher table.

    Args:
        ciphertext: Encrypted string (with row-index prefix/suffix).
        cipher: Which cipher table to use (default: TRADITIONAL).

    Returns:
        Decrypted plaintext.
    """
    if len(ciphertext) < 2:
        return ""
    ra = ord(ciphertext[0]) - 32
    rb = ord(ciphertext[-1]) - 32
    if not (0 <= ra < 20 and 0 <= rb < 20):
        return ""
    table = _CIPHER_TABLES[cipher]
    row_a = table[ra]
    row_b = table[rb]
    result = ""
    for ch in ciphertext[1:-1]:
        idx = row_b.find(ch)
        if idx == -1:
            result += ch
        else:
            result += row_a[idx]
    return result


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------

# Protocol prefix: [XWB] version=1 type=1 envelope-size=30
# Matches reference implementation's protocoltoken exactly.
_PREFIX = "[XWB]1130"


def build_connect_message(hostname: str, app_name: str) -> bytes:
    """Build the TCPConnect command message.

    Uses command token ``4`` (not RPC token ``2``), matching the
    reference implementation's ``makeRequest(..., isCommand=True)``.

    Args:
        hostname: Client hostname or IP address.
        app_name: Application name to register with the server.

    Returns:
        Encoded TCPConnect command bytes.
    """
    command_token = "4"
    name_spec = spack("TCPConnect")
    param_spec = (
        "5" + "0" + lpack(hostname) + "f" + "0" + lpack("0") + "f" + "0" + lpack(app_name) + "f"
    )
    msg = _PREFIX + command_token + name_spec + param_spec + chr(4)
    return msg.encode("utf-8")


def build_disconnect_message() -> bytes:
    """Build the ``#BYE#`` disconnect message.

    Returns:
        Encoded disconnect command bytes.
    """
    return build_rpc_message("#BYE#")


def build_rpc_message(name: str, params: list[RPCParameter] | None = None) -> bytes:
    """Build an RPC invocation message.

    Args:
        name: RPC name (max 255 characters).
        params: Ordered list of typed parameters.

    Returns:
        Encoded RPC message bytes.

    Raises:
        ValueError: If a list parameter is not the last parameter.
    """
    if params:
        for i, p in enumerate(params):
            if p.param_type == ParamType.LIST and i != len(params) - 1:
                raise ValueError("List parameter must be the last parameter")

    command_token = "2" + chr(1) + "1"
    name_spec = spack(name)
    param_spec = "5"

    if not params:
        param_spec += "4f"
    else:
        for p in params:
            if p.param_type == ParamType.LITERAL:
                param_spec += "0" + lpack(p.value) + "f"
            elif p.param_type == ParamType.LIST:
                param_spec += "2"
                first = True
                for key, val in p.entries.items():
                    if not first:
                        param_spec += "t"
                    param_spec += lpack(key) + lpack(val)
                    first = False
                param_spec += "f"

    msg = _PREFIX + command_token + name_spec + param_spec + chr(4)
    return msg.encode("utf-8")


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

# M error patterns returned as data by VistA (rather than via SNDERR)
_M_ERROR_RE = _re.compile(
    r"^(?:M  ERROR|"  # M trap errors
    r"E?Remote Procedure '.*' doesn't exist|"  # nonexistent RPC
    r"E?Remote Procedure '.*' not found)",  # alternate wording
    _re.IGNORECASE,
)


def parse_response(raw: str) -> RPCResponse:
    """Parse a raw server response into an RPCResponse.

    Transport.receive() already strips the ``\\x00\\x00`` SNDERR
    prefix from successful responses (two empty error packets per
    XWBRW.m SNDERR).  If the response still begins with a
    non-printable length byte, the error packets are extracted here
    so callers get a clean ``RPCError``.

    Additionally, some VistA errors (e.g., nonexistent RPCs, M
    traps) are returned as data rather than via SNDERR.  These are
    detected by pattern matching and raised as ``RPCError``.

    Args:
        raw: Response string after chr(4) stripping and
             null-prefix stripping performed by Transport.

    Returns:
        RPCResponse with value or lines populated.

    Raises:
        RPCError: If security or application error packet is non-empty,
            or if the data matches a known M error pattern.
    """
    if not raw:
        return RPCResponse(raw="", value="")

    data = raw

    # If the first character is a non-printable control byte
    # (ord < 32), it is the length-prefix of a SNDERR security
    # packet that was NOT stripped by Transport (i.e., an error
    # response).  Parse and raise.
    if ord(raw[0]) < 32:
        pos = 0

        # Security packet
        sec_len = ord(raw[pos])
        pos += 1
        sec_msg = raw[pos : pos + sec_len] if sec_len > 0 else ""
        pos += sec_len

        # Application error packet
        if pos < len(raw):
            err_len = ord(raw[pos])
            pos += 1
            err_msg = raw[pos : pos + err_len] if err_len > 0 else ""
            pos += err_len
        else:
            err_msg = ""

        if sec_msg:
            raise RPCError(sec_msg)
        if err_msg:
            raise RPCError(err_msg)

        data = raw[pos:]

    # Detect M errors returned as data (not via SNDERR)
    clean = data.strip().rstrip("\x00")
    if _M_ERROR_RE.match(clean):
        raise RPCError(clean)

    # Detect array vs single value
    if "\r\n" in data:
        lines = data.split("\r\n")
        # Trailing empty element from final \r\n delimiter
        if lines and lines[-1] == "":
            lines = lines[:-1]
        return RPCResponse(raw=data, lines=lines)

    return RPCResponse(raw=data, value=data)
