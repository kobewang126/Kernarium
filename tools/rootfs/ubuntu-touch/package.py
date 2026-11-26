#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Show the official download URL and package a locally supplied UBports image."""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import lzma
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from urllib.parse import urlparse

from derive import digest

DIRECTORY = Path(__file__).resolve().parent

# BEGIN GENERATED GPU PAYLOAD
EMBEDDED_GPU_RECEIPT = {'architecture': 'aarch64',
 'inputs': {'gpu-compat/CMakeLists.txt': '7938dcc4ebcbc1f4cdc02b345450f73baf64fb752fbea8ba7ff7968baa117a6a',
            'gpu-compat/build.py': 'bfcfa96a2097a034c9d2bdeb759727bcb0b86c76d59cefdfb5eeeabdcdb1a1d1',
            'gpu-compat/gpu_compat.cpp': 'bd0dc1d19f5be31960c65687ca46d61eab029f61d2b14c2e36ed73f644f9b59f',
            'sources.json': '7aee86684270834bd02727a82cf9d5209a8a16f5ebaf3465f29cadf2fd19a8c7'},
 'library_sha256': 'e67f2c3f554921855bb0ab2f6af72e130b34475cc838abdbd47a391639dcf2b1',
 'schema_version': 1}
EMBEDDED_GPU_DATA = (
    b"c-rlldvH|OeaFweceN5ofB*>yP_qJ>u?g(x#luNvSiKN*023i%YR~lS)$WzF)xLc9E=a~Us!csK<PWwc"
    b"#*Jem95+SscuZsBnwd7nHgV~se-L96GA*_MH}wpe4isb9jHT`G+<VUI-n+ZNOke-}KAP3<p6@xo-+7<="
    b"*xRvrgDgozppd^KQz=3M+`ceNvT5r`Is9Kt7MW$sNNFCfaazKov;SWBjZ9eT$b{su<Fci1^E&-x?suH~"
    b"9p~kRCEQQg3ZC@v-x*%aZI=_L^>DlG-;6N3UOC4~yKOgdTH*H{@bi*;r<&U?USFwk3G#jkE7|I;G3Sqv"
    b"&aFGhlik0({;TRu`;Yv^fBt6g?Kk6#-uU4!2+yyzjemgn2pQh!W7<6U&4=HcfAFnEZ(Qnq?a6e_r*~?z"
    b"LZ*@aX~pz;B$=NGiyiQrQzS;6R9ycL_{}b&_m_yX0e(x1=>J@z{F5d04@&5yL_6OpQNE=_c{b0!BKpD-"
    b"<r_=rua&4*DiMFKRD3*FmMH&Sv))P)<O_2#UufgR((7k(e?HBB#dXgNu8W09X<sZ6rzu0#4N3{!)V+m<"
    b"HC^kAqzp~(-qIFL#I<g<C#qR_#dBzAP^G<*xEhT-u92kCuWM?U#?pp1NTZ3+fJ;ipO_4sb-Ds?*6!H?g"
    b"X=(`K#;B(22|YskdSWyLE`|op*%b+iO8U~O9;RyOv2;Y&NI05EYH={Bp_rq9u0=I9r4g+!x+xwpB38pF"
    b">t|?yhWZDrawMikp(!+-V*Q{gRw!ja|8>&4TaOq{mtHjzC3Hu8cO)LBU0Ny~WBGl9gEXn>sRZl2F+_LO"
    b"n~k?x4JKvii6Ih=^g!UyH@@LdCH!kxvM&^(DVAzrsSwx0tD=#3dT^Dh>Y@HM&G~#Ikq-5%dL$iN6^rPr"
    b"`jTnLBAsn*w8>vjIyY}>ZQHpMuABW04FoP*S~t-Kf0LC%8~qJy^OsG{B!39Ya2l}x9=J<*!Fu6J0$a|l"
    b"WcwSGruN6SuMbrcDD{pc*0oF`Jii`(>g~fayYu`b*Ur5$P{vNd^ZD`;IcSS_IP<)holKW(@t&2Y&fODc"
    b"zL)%tYgTzVUtXNQ3P0e3m6ko`(yO^H&Of1x^xHXp|MNKSo2P7gxlKP~(`VZBvo_s+4qUM5b8Y&#O|P-("
    b"gS=hr5nzVn1h913W8E_Z6*k@DIM=3h`+aYLO}F>UXVWWe`u#TDeru_>>C<icI-6eUcy5`}t8Ds4n{My#"
    b"Hk&@nrth@r)iyn7(`P&GPgA;mUY7Wjk0<uLGdiJ=OdBDGCic90?36;!UjywLA=hS4c4n(Duh018CFfaL"
    b"@vDYqJX;QAt7T&5nQ1Sim)g?PA>C?A&xCZ3Ej<U)PutS-ApMFhy%5sx+0yqx`m!y(l+`ayrN7SVx20FG"
    b"`fX`HtKXJxWcAz9YgqkO8ty08$mg9|c+NbL&E@8^F|qfbZDSbC46M(Cbzs*Ma`hBEZe0Suy3abZD)?Pf"
    b"q%i`qn6JBh9U;G5`qkcZEmePZpzf=d=iY_#m%+F7T4%P$^p*3ztiJWj*gXB*oTnR=Bn$V=gF(6V!GJ{8"
    b"nr$8L%npN}S<kva_SIbO@UP+LBg0)mS$^<FWgt7T=e=X^KpYm6E>}MO7wDJh&%~a8uwrkQMr$C(4QTt#"
    b"N9EDym&%!&3K<($=8ZkW;+2ur?==Qao`!K(AohENtcG)}CgdTr_XSC2FOdgEWYYcTB#_-JmtAei<+{};"
    b"_MRJtILiXd4k%U10b_X}I|#8(NYH0x?${-zb_^c&J{*?UpI<`A^&8t;M#syKEWG(>>*&Ou_s#Xl{0G1X"
    b"%5|}Pdmd|BnCG#%iox~0^yeWccgj=PpZi?>3Eo40+98%<>kn(+HKk^ZwUzaawUx~$^Lr4=3f<k0M#y7*"
    b"__nPNtlhQHhqu6&_2&zPtT=bMDifUi^h}_Pta%f3^_7-vorjzlS87)H$olh8W^6=Z>A7RI5Nq5^R)?XV"
    b"%b<_1mXT%^_K~6tcgc``#`EJBefwH&FCjHo$LAke*h<KXy+pdILSK&zlgA+4#pYuPk^l6lLb^wwz6yxR"
    b"+CI+vDEd$XeG;0pZ*#|%fzQbAbIo;7Cwny_0dHm|XmG?IuN(Ge6u7=*&duDhcVCgRw<dFk{|Uz88JG)J"
    b"=hHCm(m2Vq2bLdD>dDFG!R5CvLjH9qmwR9O)fLzWp?~d!b*_v~ywB#|Gs@=u3)o9HA1xdG5@O#9c}M5N"
    b"Sl)(sL73C=`6SEcp?2Af%m|EU&`Z{^Jms~P>=m{rp)Z%9J#21*Fs`t6R=`oZx)%Ci?mMXO^87$nf>^CE"
    b"W)j3YT1mPm_O!v+)ULR(y&cA(WAs*N!zi>dV~xdvvE$I@;pt>GX$qX2dxd0R+`8cWSPf@+%^@$Doq}`n"
    b"h)f2amPoe>=PJy_&w_B?{v7<4_{y)t&99sJ+RMH_nd=^hwjYHuzkzXq`o}(C^<-^hKJLx@?Ia&_UwP&y"
    b"lVZ$k$E4S!><=M*3Vg#**QI47v+q<{X4n&W-RB{%`>F!jPi1ly&Ka{FQXe?^F_gVr9>_kO%boCf0@(nx"
    b"(^nD560qic{H`+#&l7O=k%NDIYE_1ihRh!hlTp?dDF6Dd@4<DjJQITPgEoHHQx4|<)O8Tr@$V4(25TGC"
    b"6@@g6_t|3O4QF6?ko5!d>mdIM<S&K%5RtFK`u?yE)^R`chk1O;9KWgaj_s|R&`#Ul8avlB!?CxRUpx5u"
    b"%B?-b_72-Or(wR}-L$3^)@L1@6_j`e0&rF=V`l~IC3aTq^N{Zxg%};Mc9+509R~YKVCew@Yj`=V;hrk_"
    b"K(LA&@YDoG+iPGfVC(`FB>OY7-r6xg)O+-&E!lTva>Bmf*u6!ZDXe{)Cmnn1AlqAOt$99J7p%yvoV4w&"
    b"pGsLD-&^i|dS8BgtY-r8JiwmYdt%m8Iiv73#RAH8bZ(w1=X?)=g_D1r|E5oivzL#sZ%ah?fs-#1Q~NaE"
    b"E+`sSjYuNy3ngMnxax_p_lxQIdR=cAL|UYLYa6ki%Z%H(9D5gk73>pWKLg7aUo#x4Z-Z?I%ig_fexJ)#"
    b"z~Ec}+YZ+ARWA1<u+5XX+y&e7xAb@y@eJN4Evi~#Y75vm4TxE9dv7-1RYCi<?OP4|KD8ONZRSh&s+O6)"
    b"mpm^kt<T9@Ke>2rCMevupSQUp|J+CjYj+Z~v!?IN`j@;fm$g3UIi$4xKz?3Qr+;$s<MZb}f*_R}Y}b}A"
    b">!Szyc)F-By`%3J@cTaan(xTMm$|jE0KK;I9S+|G`LWuz*&MC%7f-_b$|5#q>-c+45XPCklY0it*vYn+"
    b"Dqb#cea?HRtnCM$=atsO@(a+qi=X`Zg0oHgp)K7oH;aq5DQas+m!nOLTuz$BK3bhsJQox);;AACf*=Tj"
    b"AP9mW2!bF8f*=TjAP9mW2!bF8f*=TjAP9mW2!bF8f*=TjAP9mW2!bF8f*=TjAP9mW2!bF8f*=TjAP9mW"
    b"2!bF8f*=TjAP9mW2!bF8f*=TjAP9mW2!bF8f*=TjAP9mW2!bF8f*=TjAP9mW2!bF8f*=TjAP9mW2!bF8"
    b"f*=TjAP9mW2!bF8f*=TjAP9mW2!bF8f*=TjAP9mW2!bF8f*=Tj{C^Uxv}`rE64xV=Gd<`^KkG^#<QFq}"
    b"`X@YH#nb)MEIWgzpO|ggukrNAgypb^rz^N!$n7znzu1+3b267;_8PCRO!UiRSuaofWXn$H>07)!?>1S$"
    b"t-|f+IjaD7BinfS8lEoacE0ehaO(G$JKK4U+i9-)CUaK%_w$D4c-kZUczP$#&+@eLzqB5XPe}ix@rI}U"
    b"-`Zq;#w<G9+P>+#e@9O`Zlrw;P5vf-{i-!-Guil5W3#`$+28O0&$wG(6j<$Nq++_9Uw=+r$*()7?#ZuD"
    b"r(TwyXQ%GXuMekQo?mB9y&}IJo%*!=K6L8S^W*2#E6MQmVtQ46|2p*<<X};KCRsVBm_CaP7uBmtdrdKY"
    b"cK)1j>T~kvgHxYdbUiDui;w4u>9zTN@6_iNtSd{OPlk)?3ko#J+|$={ZoPt^Lhf;{G|!$Xy~a_#a2_l8"
    b"Y3rVs1$V4>8W}7RXTK}XlDo8j#MS;4y!~!{CD+fo^!4Wd!f|fp<;DF;u+tpVsqvQ_aSGQ%*ep}1AK>wW"
    b"mBrdqxZVz%aSC;-{48>4PO&(J>*TGwjAzo-o?q~G3jHkCf6Mg%ztNs{)LXb8MSJ$U+EXD}<0*7;7(T%D"
    b"x4ABkt&LniCF1ZKQb_2E?706u%k?uZ{cpH_)}?>I^$RZj3fIS7dbw=rpSyIit_EHG74vm_&b_U3Q9j^0"
    b"mmV<dE!0VgIBR9=Dam~v{*f7{aQ#2bb<uv&uawN@y>Pz|nR?;*u-A-pJ?B0T_w)Gf^?68?cb$h7{3*(P"
    b"zZjF*t}EnB3H>uuuOuG+K)8}u^QFvoT_JOo;&GZlUs^=pQlfmcgnqb$eoV32S<fGASMp(ct3>&aO6b2W"
    b"p?f`6{9v_}Ud+egYoPmzlwa*B9;dT}{wF2$CriZtzNh&3zg(g`3F$_}pCHQzNl1-G>26IOpuKS>$3X^@"
    b"GSa=h{tyXky4Dv-8JbRw7!5@eaV<rbhY6+O1nr9^dekTl8wou{)ieZ4#FA0X(8BOoR<s1|jl?5V)pd1<"
    b"YH>p!BE7mA(`Yyyiw%K`Ek&WE;V9adOjA~aYWPFRB%zONZD^#On;&Xz*-YtH+OTey8jXZiL+jYKYkNH{"
    b"EbyQx5H3}sp^;S;(NbH|hBnwyq(HsdmbL^uix$aV%iUR4=XW1zSlibFqo!+6Ck<=6A|b6~T|$raMdE4{"
    b"irlpTi_xU@MK{4%M4<7HyZ!Hw$$Zzb@K#(fDML>TxdPm!1l`cpvZaG|Y;C77T(ooR4%)GiiyPa!*es_K"
    b"v|o*fqZ(;{*sp87eoFfW2We8%QwfL>F^1?aSPpFFi8-l+w*T?gmMxpwz`J`(n+VQ_@u3YHws&;X?v~cg"
    b"9h4-Eei)oEjj{Ql(L`t<(7Ab2Ya4C!H>?H!l%a+OXs92SuNsNk^9lymQMxa!>S23vXGQ6FVO60)m36`#"
    b"=)xQ`Al0>~rlzz&+s>UWt($0rzX=9;yU|!rDa23grl}#=OEIeHI*hRuW#>-X<cAlU1`>{@hGO~9P0hqH"
    b"xg-W#H4&oel-d*3Xv)=$a5RzB;&$(1^I&gT;mi}dse22Z+Ve0wY{z%A3Q6y7Jz_X}z9YUn5)acZEtQTz"
    b"PFovoGI##efT*Fz(h=P`Aha)*h_kuS4Vd?o0rlyQu&fb9n?U?9K!(}_*3d26FRtPVL-Y5=)Bc`xBpO~7"
    b"2@^BbucrEmKRgr%Ps<v*m9q;5CX$Fd5)|@a4pml=UnQdk@te!m4=V%yn+w^mC*UAaiC^pIhgN@BpGrZ{"
    b"P>5=SAuVZ8!)&{M>O8Yzh-;`yjYUG>k}%AFR+U!xo>YqX;n0i0!SdgKuV2K!b%>`1@m?(K@`7g}Cw_LX"
    b"&*c)rU%WpHTkrZF<9?l8mw!ice%}!`AWzk+*!;ztS%B-Z>wA%~x1_@NH#-~ow;JIu-rI$Bw_kSI9sJvm"
    b"NQ?J-VMlD^<|)$uFxO?*_a<Sll^8$K|2X$=b$!1QR($Vb{<TH?2l<$IUElYFU2vEAPr3Zv-*ManUhVRK"
    b"%I!bhX}|K`*?*tQUpz+(TXUE8e~<e&itnGZo%Y3|?{!n%`b&N-=1;s22-|&^`bS*;;ya44r={Zc=bzVI"
    b"{^EO!uye_s*Z<%1Z@r4^`|Zd?@%k!U_Kf*9HRUhf%a7fo|3`f86xVml;}gz}=5hInb#RgQDeuqUbB^bx"
    b"&X+sYf7#_Pz8ihc{rBI+|EkMhy!R#fNLQ0P&);>f34ihaHq8B#%ANhc<n_BhdJ6wlCFb95<znBDd5QXI"
    b"Q{V5m6gfYpmH37|KF#uf+jHmjH@k%Y3p1^fxx1|2{{mkw9SH"
)
# END GENERATED GPU PAYLOAD


def stage_gpu(destination: Path) -> None:
    sys.path.insert(0, str(DIRECTORY / 'gpu-compat'))
    from artifact import read_artifact
    data = zlib.decompress(base64.b85decode(EMBEDDED_GPU_DATA))
    if hashlib.sha256(data).hexdigest() != EMBEDDED_GPU_RECEIPT['library_sha256']:
        raise ValueError('embedded GPU library checksum differs')
    if destination.exists():
        if read_artifact(destination) != data:
            raise ValueError('GPU cache differs from the embedded artifact; select a new work directory')
        return
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix='.gpu-stage-') as directory:
        temporary = Path(directory) / 'artifact'
        (temporary / 'lib').mkdir(parents=True)
        (temporary / 'lib/libtoucharium-mir-gpu.so').write_bytes(data)
        (temporary / 'receipt.json').write_text(json.dumps(EMBEDDED_GPU_RECEIPT, indent=2) + '\n')
        read_artifact(temporary)
        temporary.rename(destination)


def publish(source: Path, destination: Path) -> None:
    # An interrupted or concurrent run must not replace an accepted input.
    os.link(source, destination)
    source.unlink()


def decompress(archive: Path, disk: Path, size: int, expected: str) -> None:
    if disk.exists():
        if disk.stat().st_size != size or digest(disk) != expected:
            raise ValueError('cached raw disk differs from the pinned official input')
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=disk.parent, prefix='.raw-', delete=False) as stream:
            temporary = Path(stream.name)
            checksum = hashlib.sha256()
            total = 0
            deadline = time.monotonic() + 1800
            with lzma.open(archive, 'rb') as source:
                while block := source.read(8 << 20):
                    total += len(block)
                    if total > size or time.monotonic() >= deadline:
                        raise ValueError('decompressed disk exceeds the pinned size or time bound')
                    checksum.update(block)
                    stream.write(block)
            if total != size or checksum.hexdigest() != expected:
                raise ValueError('decompressed raw disk identity differs from the pinned input')
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o644)
        publish(temporary, disk)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--archive', type=Path, help='official .raw.xz archive downloaded by the user')
    inputs.add_argument('--disk', type=Path, help='already decompressed official raw disk')
    parser.add_argument('--work', type=Path, help='persistent local cache and build directory')
    parser.add_argument('--output', type=Path, help='new output .erofs image')
    options = parser.parse_args()
    specification = json.loads((DIRECTORY / 'sources.json').read_text())
    if options.archive is None and options.disk is None:
        print('Download the official input in your browser:')
        print(specification['archive']['url'])
        print('Archive SHA-256: ' + specification['archive']['sha256'])
        print('Then run this script on Linux with --archive FILE --work DIR --output IMAGE.erofs.')
        return
    if options.work is None or options.output is None:
        parser.error('--work and --output are required when an input is supplied')
    if platform.system() != 'Linux' or os.geteuid() != 0:
        parser.error('run with sudo on Linux; macOS requires a Linux VM')
    output = options.output.resolve()
    receipt = output.with_suffix(output.suffix + '.json')
    catalog = output.with_suffix(output.suffix + '.import.json')
    if output.suffix != '.erofs' or any(path.exists() for path in (output, receipt, catalog)):
        parser.error('choose a new .erofs output with no existing image, receipt or import descriptor')
    work = options.work.resolve()
    gpu = work / 'gpu-compat'
    required = ['mount', 'umount', 'mkfs.erofs', 'fsck.erofs']
    missing = [tool for tool in required if shutil.which(tool) is None]
    if missing:
        parser.error('missing tools: ' + ', '.join(missing)
                     + '; on Ubuntu install python3 erofs-utils util-linux')
    work.mkdir(parents=True, exist_ok=True)
    with (work / '.package.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('another packaging process is using this work directory')
        source = specification['archive']
        cache = work / 'input'
        cache.mkdir(exist_ok=True)
        disk = options.disk.resolve() if options.disk else cache / Path(urlparse(source['url']).path).stem
        archive = options.archive.resolve() if options.archive else None
        if archive is not None and (not archive.is_file() or digest(archive) != source['sha256']):
            raise ValueError('archive SHA-256 differs from the pinned official input')
        if options.disk and not disk.is_file():
            raise ValueError('the supplied raw disk does not exist')
        needed = (0 if disk.exists() else specification['disk']['size']) + (8 << 30)
        if shutil.disk_usage(work).free < needed:
            raise ValueError('insufficient work storage; allow raw-disk size plus 8 GiB for a first run')
        print('Verifying the embedded ARM64 GPU compatibility library', flush=True)
        stage_gpu(gpu)
        print('Verifying the official raw disk', flush=True)
        decompress(archive, disk, specification['disk']['size'], specification['disk']['sha256'])
        # derive.py owns mount cleanup and its bounded mkfs/fsck subprocesses.
        # Keep that cleanup in this process instead of timing out a parent
        # subprocess while its disposable mounts are still active.
        import derive
        previous = sys.argv
        try:
            sys.argv = [str(DIRECTORY / 'derive.py'), '--disk', str(disk), '--gpu-compat', str(gpu),
                        '--output', str(output), '--work-root', str(work / 'mounts')]
            derive.main()
        finally:
            sys.argv = previous
        subprocess.run([sys.executable, '-B', str(DIRECTORY / 'accept-image.py'),
                        '--image', str(output), '--receipt', str(receipt), '--catalog', str(catalog)],
                       check=True, timeout=180)
        print('Image: ' + str(output), flush=True)
        print('Producer receipt: ' + str(receipt), flush=True)
        print('Import descriptor: ' + str(catalog), flush=True)
        print('The current app accepts its bundled descriptor only. A locally generated image is not'
              ' automatically accepted; it needs matching app import support or an app build using'
              ' this import descriptor.', flush=True)


if __name__ == '__main__':
    main()
