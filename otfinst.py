#!/usr/bin/env python

# otfinst version 1.0.5 25 Apr 2022
# http://www.ece.ucdavis.edu/~jowens/code/otfinst/
# Formerly known as otftex_install
#
# usage: As arguments, takes OTF font files or directories where the
# OTF font files are located. Configuration is within this file.

# Copyright (c) 2005-22, John Owens <jowens at ece.ucdavis.edu>,
# University of California, Davis. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# Neither the name of the University of California nor the names of
# its contributors may be used to endorse or promote products derived
# from this software without specific prior written permission. THIS
# SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import sys
import os
import re
import math
import time
import datetime
import operator
import glob
import subprocess

#######################################
# BEGIN USER-SETTABLE VARIABLES
#######################################

# which encoding are we using?
encoding = "LY1"

# "encoding" (above) should have a dict entry in "encodings" that specifies
#   the two-letter berry designation for the encoding and the command-line
#   options to otftotfm that work for the encoding
encodings = {
    "LY1": {
        "berryencoding": "8y",
        "commandline": "-e texnansx",
    },
}

# kpsewhich will look up the right TEXMFHOME directory, but within that,
#   where do local fonts go?
localfontsdir = "/tex/latex/localfonts/"

# which OpenType options do we support in this script?
# add more to optionList if you want the script to support them
optionList = [
    # in optionList, each element is itself a list
    # we generate options by always picking one choice from each element
    # and taking all permutations of those choices
    ["kern"],  # always selected
    ["liga"],
    ["lnum", "onum", "swsh", "sinf", "sups", "pnum", "fakenum"],  # one of these
    ["smcp", ""],  # either smcp or nothing
]

# categorize the OpenType options above
# globalOptionList contains options that we should apply to all fonts
globalOptionList = ["kern", "liga"]
# newFontFamilyOptionList has options that create new font families
newFontFamilyOptionList = ["lnum", "onum", "swsh", "sinf", "sups", "pnum", "fakenum"]
# weightOptionsList contains options that modify the weight
weightOptionList = []
# widthOptionsList contains options that modify the width
widthOptionList = []
# variantOptionsList contains options that modify the variant
variantOptionList = ["smcp"]
# fakeOptionList contains options that aren't real OpenType options
fakeOptionList = ["fakenum"]  # fakenum is if no ?num is available

# options and their Berry encodings
# contains both:
# - features (4 letters) and their mappings (lnum, onum, smcp)
#   (found in otfinfo --features)
# - subfamily attributes (italic, bold, etc.)
#   (found in otfinfo --info, subfamily field)
optionMappings = {
    # OpenType command line options
    "lnum": "x",
    "onum": "j",
    "fakenum": "",  # we manually put this in if neither lnum
    # nor onum are present so we get
    # something out
    "swsh": "w",
    "sinf": "0",
    "sups": "1",
    "pnum": "2",
    "smcp": "sc",  # also a variant
    # weights
    "thin": "ul",
    "extralight": "el",
    "light": "l",
    "book": "m",
    "medium": "mb",
    "demibold": "db",
    "semibold": "sb",
    "bold": "b",
    "extrabold": "eb",
    "black": "eb",
    "heavy": "eb",
    # widths
    "condensed": "c",
    "cond": "c",
    "cn": "c",
    "narrow": "n",
    "semicondensed": "sc",
    "semiextended": "sx",
    "extended": "x",
    # variants
    "italic": "it",
    "it": "it",
    "slanted": "sl",
    "oblique": "sl",
    "outline": "ol",
    # regular is the default
    "regular": "",
}

# each font has a 3-letter designation
# it's the first 3 letters from
# http://www.tex.ac.uk/tex-archive/info/fontname/adobe.map
# font names are what's returned from "otfinfo --family fontfile.otf"
berryname = {
    "Minion Pro": "pmn",
    "Myriad Pro": "pmy",
    "Adobe Garamond Pro": "pag",
    "Garamond Premier Pro": "pad",
    "Adobe Caslon Pro": "pac",
    "Adobe Jenson Pro": "paj",
    "Adobe Text Pro": "ptx",
    "Adobe Monospace": "pt9",
    "Utopia Std": "put",
    "Warnock Pro": "pwp",
    "Kepler Std": "pkp",
    "Prestige Elite Std": "ppe",
    "Calibri": "jk0",
    "Cambria": "jk1",
    "Candara": "jk2",
    "Consolas": "jk3",
    "Constantia": "jk4",
    "Corbel": "jk5",
    "MetaPro": "0m2",
    "Arno Pro": "pa0",
    "ScalaSansPro": "0sa",
    "Hypatia Sans Pro": "phy",
    "ITC Berkeley Oldstyle Std": "iby",
    "Zapfino Extra LT Pro": "lzf",
    "Bickham Script Std": "pik",
    "CaslonAntique": "9ca",
    "FlemishScript BT": "bf0",
    "Liberation Sans": "fla",
    "Liberation Serif": "flr",
    "Liberation Mono": "flm",
    "Montag": "fm9",
    "Times NR MT Std": "mnt",
    "Bree": "fe3",
    "Ronnia": "fr5",
    "Sabon LT Std": "lsb",  # thanks Ingo Struck
    "Inconsolata": "fi4",
    "Inconsolata XL": "fix",
    "Hack": "fhk",
    "QuioscoOne": "fq1",
    # http://tex.stackexchange.com/questions/23592/berry-naming-scheme-list-of-latex-font-families
    "TeX Gyre Bonum": "qbk",
    "TeX Gyre Pagella": "qpl",  # XXX FIXME what to do with math
    "TeX Gyre Termes": "qtm",
    "TeX Gyre Heros": "qhv",
    "TeX Gyre Heros Cn": "qhx",  # XXX FIXME merge with Heros
    "TeX Gyre Cursor": "qcr",
    "TeX Gyre Schola": "qcs",
    "TeX Gyre Adventor": "qag",
    "TeX Gyre Chorus": "qzc",
}

# if you would like to scale the font by default, set it here as a float
scaled = {}  # 'Minion Pro' : 1.0,

#######################################
# END USER-SETTABLE VARIABLES
#######################################

#######################################
# BEGIN UTILITY FUNCTIONS
#######################################


def letterize(s):
    s = s.replace("0", "zero")
    s = s.replace("1", "one")
    s = s.replace("2", "two")
    s = s.replace("3", "three")
    s = s.replace("4", "four")
    s = s.replace("5", "five")
    s = s.replace("6", "six")
    s = s.replace("7", "seven")
    s = s.replace("8", "eight")
    s = s.replace("9", "nine")
    return s


glyfRE = re.compile("glyf")
CFFRE = re.compile("CFF")
# User can redefine if necessary; used to prune candidate list of fonts


def isValidFontFile(filename):
    # return os.system("otfinfo --info -q %s" % filename) == 0
    p = subprocess.Popen(
        ["otfinfo", "-qt", filename],  # "'%s'" % filename],
        universal_newlines=True,
        stdout=subprocess.PIPE,
    )
    output, _ = p.communicate()

    # otfinfo -qt returns the fields in the font file; "glyf" means TrueType
    # and "CFF" means PostScript
    for line in output.split(os.linesep):
        if glyfRE.search(line):
            print("%s (TTF)" % filename)
            return True
        if CFFRE.search(line):
            print("%s (PS)" % filename)
            return True
    return False


# Eddie Kohler's shell script for determining OTF type
# otfflavor () {
#      # Returns 0 for not OTF, 1 for CFF-flavored, 2 for TTF-flavored
#      otfinfo -qt $1 | awk '/glyf/ { exit 2 }
# /CFF/ { exit 1 }'
# }


def generateFontfiles(l):
    # Get all candidate files. This works as follows:
    # 1) glob the input list, resulting in a list
    # 2)a) if anything in that list is a file, add it to the fontfiles list
    # 2)b) if anything in that list is a dir, add its subfiles to
    #      the fontfiles list
    # start off assuming everything is a dir
    gl = []
    fontfiles = []
    for item in l:
        gl += glob.glob("%s*" % item)
    for item in gl:
        if os.path.isdir(item):
            for file in os.listdir(item):
                fontfiles.append(os.path.join(item, file))
        if os.path.isfile(item):
            fontfiles.append(item)
    debug = True
    if debug:
        print("Candidate font files are: ", fontfiles)
    print("Installing following font files:")
    fontfiles = list(filter(isValidFontFile, fontfiles))
    return fontfiles


# http://www.microsoft.com/typography/otspec/recom.htm
# We recommend using name ID's 8-12, to identify manufacturer,
# designer, description, URL of the vendor, and URL of the designer.
# URL's must contain the protocol of the site: for example, http:// or
# mailto: or ftp://. The OpenType font properties extension can
# enumerate this information to the users.
#
# The Subfamily string in the 'name' table should be used for variants
# of weight (ultra light to extra black) and style (oblique/italic or
# not). So, for example, the full font name of "Helvetica Narrow
# Italic" should be defined as Family name "Helvetica Narrow" and
# Subfamily "Italic". This is so that Windows can group the standard
# four weights of a font in a reasonable fashion for
# non-typographically aware applications which only support
# combinations of "bold" and "italic."
#
# The Full font name string usually contains a concatenation of
# strings 1 and 2. However, if the font is 'Regular' as indicated in
# string 2, then use only the family name contained in string 1. This
# is the font name that Windows will expose to users.

otfinfoversionRE = re.compile("([0-9]+\.[0-9]+)")
otfinfoRE = re.compile("^(.*):\s+(.*)$")
urlRE = re.compile("(\w*)\.(com|net|org|edu|de|fr|co\.uk)")
opticalRE = re.compile("size range \(([\d.]+) pt, ([\d.]+) pt\]")

# list-to-string and string-to-list primitives (useful when we want to
# index into a hash with a list - we use a string instead)
sep = "-"


def l2s(l):
    return sep.join(l)


def s2l(s):
    if not s:
        return []
    return s.split(sep)


# otfinfo requires version 2.38 or higher of otfinfo (which supports --info)
# TODO: does not properly recognize 2.100+


def checkOTFInfoVersion():
    p = subprocess.Popen(
        ["otfinfo", "--version"], universal_newlines=True, stdout=subprocess.PIPE
    )
    output, _ = p.communicate()
    otfiv = output.strip()
    m = otfinfoversionRE.search(otfiv)
    if float(m.group(1)) < 2.38:
        sys.stderr.write(
            "Your otfinfo version is currently %s.\nPlease upgrade your otfinfo version to at least 2.38.\n"
            % m.group(1)
        )
        sys.exit()


# given a font file, populates fonthash for that font file
# calls classifyFont on each font file too


def addToFonthash(font):
    p = subprocess.Popen(
        ["otfinfo", "--postscript-name", font],
        universal_newlines=True,
        stdout=subprocess.PIPE,
    )
    output, _ = p.communicate()
    postScriptName = output.strip()
    fonthash[postScriptName] = {}
    fonthash[postScriptName]["filename"] = font
    print("PS name is %s, font is %s" % (postScriptName, font))
    p = subprocess.Popen(
        ["otfinfo", "--info", font], universal_newlines=True, stdout=subprocess.PIPE
    )
    output, _ = p.communicate()
    info = output.strip()
    for line in info.split(os.linesep):
        m = otfinfoRE.search(line)
        if m:
            if (m.group(1) == "Family") or (m.group(1) == "Preferred family"):
                # 'preferred family' preferred over 'family'; relies on it coming last
                # which it should under otfinfo
                fonthash[postScriptName]["family"] = m.group(2)
            elif (m.group(1) == "Subfamily") or (m.group(1) == "Preferred subfamily"):
                # 'preferred subfamily' preferred over 'subfamily'; relies on
                # it coming last which it should under otfinfo
                # this RE separates both 'Aa Bb' and 'AaBb' into ['aa', 'bb']
                fonthash[postScriptName]["subfamily"] = (
                    re.sub("(?<=[a-z])(?=[A-Z])", " ", m.group(2)).lower().split()
                )
                if "roman" in fonthash[postScriptName]["subfamily"]:
                    # replace 'roman' with 'regular'
                    roman_id = fonthash[postScriptName]["subfamily"].index("roman")
                    fonthash[postScriptName]["subfamily"][roman_id] = "regular"
                while "extra" in fonthash[postScriptName]["subfamily"]:
                    # if we see 'extra x', combine 'extra' with 'x' (next element),
                    # delete 'extra'
                    extra_id = fonthash[postScriptName]["subfamily"].index("extra")
                    fonthash[postScriptName]["subfamily"][extra_id + 1] = (
                        "extra" + fonthash[postScriptName]["subfamily"][extra_id + 1]
                    )
                    fonthash[postScriptName]["subfamily"].remove("extra")
            elif m.group(1) == "Vendor URL":
                fonthash[postScriptName]["vendor"] = urlRE.search(m.group(2)).group(1)
    if "vendor" not in list(fonthash[postScriptName].keys()):
        fonthash[postScriptName]["vendor"] = "generic"

    p = subprocess.Popen(
        ["otfinfo", "--features", font], universal_newlines=True, stdout=subprocess.PIPE
    )
    output, _ = p.communicate()
    features = output.strip()

    p = subprocess.Popen(
        ["otfinfo", "--optical-size", font],
        universal_newlines=True,
        stdout=subprocess.PIPE,
    )
    output, _ = p.communicate()
    opticalSize = output.strip()
    m = opticalRE.search(opticalSize)
    if m:
        # convert from OTF's (exclusive, inclusive] to TeX's [inclusive, exclusive)
        # OTF measures in decipoints, so add 0.1 to each size
        fonthash[postScriptName]["opticalSize"] = [
            str(float(m.group(1)) + 0.1),
            str(float(m.group(2)) + 0.1),
        ]
    else:
        fonthash[postScriptName]["opticalSize"] = []
    fonthash[postScriptName]["weight"] = []
    fonthash[postScriptName]["width"] = []
    fonthash[postScriptName]["variant"] = []
    for s in fonthash[postScriptName]["subfamily"]:
        if s in [
            "regular",
            "thin",
            "extralight",
            "light",
            "book",
            "medium",
            "regular",
            "demibold",
            "semibold",
            "bold",
            "extrabold",
            "black",
            "heavy",
        ]:
            fonthash[postScriptName]["weight"].append(s)
        if s in [
            "regular",
            "condensed",
            "cond",
            "cn",
            "semicondensed",
            "narrow",
            "semiextended",
            "extended",
        ]:
            fonthash[postScriptName]["width"].append(s)
        if s in ["regular", "italic", "it", "slanted", "oblique", "outline"]:
            fonthash[postScriptName]["variant"].append(s)
    fonthash[postScriptName]["weight"].sort()
    fonthash[postScriptName]["width"].sort()
    fonthash[postScriptName]["variant"].sort()
    fonthash[postScriptName]["weight"] = l2s(fonthash[postScriptName]["weight"])
    fonthash[postScriptName]["width"] = l2s(fonthash[postScriptName]["width"])
    fonthash[postScriptName]["variant"] = l2s(fonthash[postScriptName]["variant"])
    numFeatureCount = 0
    fonthash[postScriptName]["features"] = []
    for line in features.split(os.linesep):
        if line[1:4] == "num":
            numFeatureCount += 1
        fonthash[postScriptName]["features"].append(line[0:4])
    if numFeatureCount == 0:
        fonthash[postScriptName]["features"].append("fakenum")
        # if no other ?num are present, add 'fakenum'
    classifyFont(postScriptName)


# populates classifiedFonts from fonthash


def classifyFont(postScriptName):
    # classifiedFonts[postScriptName][weight][width][variant] contains list of
    # opticals
    family = fonthash[postScriptName]["family"]
    weight = fonthash[postScriptName]["weight"]
    width = fonthash[postScriptName]["width"]
    variant = fonthash[postScriptName]["variant"]
    if family not in list(classifiedFonts.keys()):
        classifiedFonts[family] = {}
    if weight not in list(classifiedFonts[family].keys()):
        classifiedFonts[family][weight] = {}
    if width not in list(classifiedFonts[family][weight].keys()):
        classifiedFonts[family][weight][width] = {}
    if variant not in list(classifiedFonts[family][weight][width].keys()):
        classifiedFonts[family][weight][width][variant] = []
    classifiedFonts[family][weight][width][variant].append(
        [postScriptName, fonthash[postScriptName]["opticalSize"]]
    )


# generates Berry series from list of series options


def buildSeries(weight, width):
    seriesopts = unique(s2l(weight) + s2l(width))
    if l2s(seriesopts) == "regular" or not seriesopts:
        return "m"
    series = ""
    for s in seriesopts:
        series += optionMappings[s]
    return series


# generates Berry shape from list of shape options


def buildShape(variant):
    shapeopts = unique(s2l(variant))
    if l2s(shapeopts) == "regular" or not shapeopts:
        return "n"
    shape = ""
    if ("italic" in shapeopts) and ("smcp" in shapeopts):
        shapeopts.remove("italic")
        shapeopts.remove("smcp")
        shape += "si"
    for s in shapeopts:
        shape += optionMappings[s]
    return shape


# populates explodedFonts from classifiedFonts


def populateFontDataStructures():
    for family in list(classifiedFonts.keys()):
        for weight in list(classifiedFonts[family].keys()):
            for width in list(classifiedFonts[family][weight].keys()):
                for variant in list(classifiedFonts[family][weight][width].keys()):
                    for font in classifiedFonts[family][weight][width][variant]:
                        name = font[0]
                        myOptionList = []
                        for o in optionList:
                            opt = []
                            for oo in o:
                                if not oo or oo in fonthash[name]["features"]:
                                    opt.append(oo)
                            if opt:
                                myOptionList.append(opt)
                        for o in breakout(myOptionList):
                            xfamily = [fonthash[name]["family"]]
                            xweight = weight
                            xwidth = width
                            xvariant = variant
                            cmdlineoptions = []
                            for oo in o:
                                if oo in globalOptionList and oo not in fakeOptionList:
                                    cmdlineoptions.append(oo)
                                if (
                                    oo in newFontFamilyOptionList
                                    and oo not in fakeOptionList
                                ):
                                    xfamily.append(oo)
                                if oo in weightOptionList and oo not in fakeOptionList:
                                    xweight = l2s(s2l(weight) + [oo])
                                    cmdlineoptions.append(oo)
                                if oo in widthOptionList and oo not in fakeOptionList:
                                    xwidth = l2s(s2l(width) + [oo])
                                    cmdlineoptions.append(oo)
                                if oo in variantOptionList and oo not in fakeOptionList:
                                    xvariant = l2s(s2l(variant) + [oo])
                                    cmdlineoptions.append(oo)
                            xfamily = l2s(xfamily)
                            # print name, xfamily, xweight, xwidth, xvariant, cmdlineoptions
                            # print l2s([encoding, name] + s2l(xfamily)[1:] + cmdlineoptions),
                            # for f in (s2l(xfamily)[1:] + cmdlineoptions):
                            # print '-f%s' % f,
                            # print
                            # print xfamily, '|', xweight, '|', xwidth, '|',
                            # buildSeries(xweight, xwidth), '|', xvariant, '|',
                            # buildShape(xvariant), '|', name
                            series = buildSeries(xweight, xwidth)
                            shape = buildShape(xvariant)
                            optical = l2s(fonthash[name]["opticalSize"])
                            if xfamily not in list(explodedFonts.keys()):
                                explodedFonts[xfamily] = {}
                            if series not in list(explodedFonts[xfamily].keys()):
                                explodedFonts[xfamily][series] = {}
                            if shape not in list(explodedFonts[xfamily][series].keys()):
                                explodedFonts[xfamily][series][shape] = {}
                            if optical not in list(
                                explodedFonts[xfamily][series][shape].keys()
                            ):
                                explodedFonts[xfamily][series][shape][optical] = {}
                            explodedFonts[xfamily][series][shape][optical][
                                "filename"
                            ] = fonthash[name]["filename"]
                            explodedFonts[xfamily][series][shape][optical][
                                "family"
                            ] = fonthash[name]["family"]
                            explodedFonts[xfamily][series][shape][optical][
                                "vendor"
                            ] = fonthash[name]["vendor"]
                            explodedFonts[xfamily][series][shape][optical][
                                "fontname"
                            ] = l2s(
                                [encoding, name] + s2l(xfamily)[1:] + cmdlineoptions
                            )
                            explodedFonts[xfamily][series][shape][optical][
                                "cmdlineoptions"
                            ] = ""
                            for f in s2l(xfamily)[1:] + cmdlineoptions:
                                explodedFonts[xfamily][series][shape][optical][
                                    "cmdlineoptions"
                                ] += ("-f%s " % f)


# generates .fd files for each font family, .sty file for the typeface
# does the right thing if multiple typefaces/font families
# requires that explodedFonts is populated


def generateFDandSTY():
    styfiles = {}
    for family in list(explodedFonts.keys()):
        fontbase = s2l(family)[0]
        fontoptions = s2l(family)[1:]
        if fontbase in list(styfiles.keys()):
            styfiles[fontbase].append(fontoptions)
        else:
            styfiles[fontbase] = [fontoptions]
        fdfilebase = encoding.lower()
        if fontbase not in list(berryname.keys()):
            sys.stderr.write(
                "Error: The three-letter Berry ID for font '%s' must be\n  added to the 'berryname' hash. Please add it as '%s': 'xxx',\n  replacing 'xxx' with the three-letter Berry ID.\n"
                % (fontbase, fontbase)
            )
            sys.exit()
        fontname = berryname[fontbase]
        for o in fontoptions:
            fontname += optionMappings[o]
        fdfilebase += fontname
        print("Generating", (fdfilebase + ".fd"))
        texmfhome = filenameInLocaldir(fdfilebase + ".fd")
        print(texmfhome)
        fddest = open(texmfhome, "w")
        print(
            (
                "%% Autogenerated by %s on %s"
                % (sys.argv[0], datetime.date.today().strftime("%Y/%m/%d"))
            ),
            file=fddest,
        )
        longsuffix = fontoptions
        print(
            (
                "\ProvidesFile{%s.fd}[%s %s/%s]"
                % (
                    fdfilebase,
                    datetime.date.today().strftime("%Y/%m/%d"),
                    encoding,
                    family,
                )
            ),
            file=fddest,
        )
        # example of scaling from Helvetica:
        # \expandafter\ifx\csname Hv@scale\endcsname\relax
        #  \let\Hv@@scale\@empty
        # \else
        #  \edef\Hv@@scale{s*[\csname Hv@scale\endcsname]}%
        # \fi
        print(
            r"\expandafter\ifx\csname %s@scaled\endcsname\relax"
            % letterize(berryname[fontbase]),
            file=fddest,
        )
        if fontbase in list(scaled.keys()):
            print(
                r"  \edef\%s@scaled{s*[%f]}%%"
                % (letterize(berryname[fontbase]), scaled[fontbase]),
                file=fddest,
            )
        else:
            print(
                r"  \let\%s@scaled\@empty" % letterize(berryname[fontbase]), file=fddest
            )
        print(r"\fi", file=fddest)
        print("\n\\DeclareFontFamily{%s}{%s}{}" % (encoding, fontname), file=fddest)
        for se in list(explodedFonts[family].keys()):
            for sh in list(explodedFonts[family][se].keys()):
                print(
                    (
                        "\\DeclareFontShape{%s}{%s}{%s}{%s}{"
                        % (encoding, fontname, se, sh)
                    ),
                    file=fddest,
                )
                opticalkeys = list(explodedFonts[family][se][sh].keys())
                sz = len(opticalkeys)
                if sz > 1:
                    # sort by size range
                    opticalkeys.sort(key=lambda a: float(a.split("-")[0]))

                    # then lop off the lowest start point and highest end point
                for op in opticalkeys:
                    if sz > 1:
                        range = op
                        if range == opticalkeys[0]:
                            range = "-" + range.split("-")[1]
                        elif range == opticalkeys[-1]:
                            range = range.split("-")[0] + "-"
                        print("  <%s> " % range, end=" ", file=fddest)
                    else:
                        print("  <-> ", end=" ", file=fddest)
                    print(
                        "\%s@scaled " % letterize(berryname[fontbase]),
                        end=" ",
                        file=fddest,
                    )
                    print(
                        "%s" % explodedFonts[family][se][sh][op]["fontname"],
                        file=fddest,
                    )
                    # example command line:
                    # otftotfm -a -e texnansx --no-create /Volumes/Adobe\ Type\
                    # Classics/Western\ Fonts/Adobe\ Caslon\
                    # Pro/ACaslonPro-Regular.otf -fkern -fliga
                    # LY1--AdobeCaslonPro-Regular

                    installcommands.append(
                        'otftotfm --no-updmap -a %s --typeface "%s" --vendor "%s" "%s" %s %s'
                        % (
                            encodings[encoding]["commandline"],
                            niceFontName(explodedFonts[family][se][sh][op]["family"]),
                            explodedFonts[family][se][sh][op]["vendor"],
                            explodedFonts[family][se][sh][op]["filename"],
                            explodedFonts[family][se][sh][op]["cmdlineoptions"],
                            explodedFonts[family][se][sh][op]["fontname"],
                        )
                    )
                print("}{}", file=fddest)
        # rest of fd part:
        # - substitutes slanted with italic if slanted not available
        # - substitutes italic with slanted if italic not available
        # - substitutes bold extended with bold if bold extended not available
        # - substitutes bold extended slanted with bxit if bxsl not available
        for sh in [["sl", "it"], ["it", "sl"]]:
            # sh[0] is replacement sh, sh[1] is old sh
            for se in list(explodedFonts[family].keys()):
                if sh[0] in list(explodedFonts[family][se].keys()) and sh[
                    1
                ] not in list(explodedFonts[family][se].keys()):
                    print(
                        (
                            "\\DeclareFontShape{%s}{%s}{%s}{%s}{"
                            % (encoding, fontname, se, sh[1])
                        ),
                        file=fddest,
                    )
                    print("  <->  sub * %s/%s/%s" % (fontname, se, sh[0]), file=fddest)
                    print("}{}", file=fddest)

        if "b" in list(explodedFonts[family].keys()) and "bx" not in list(
            explodedFonts[family].keys()
        ):
            se = "b"
            for sh in explodedFonts[family][se]:
                print(
                    (
                        "\\DeclareFontShape{%s}{%s}{%s}{%s}{"
                        % (encoding, fontname, "bx", sh)
                    ),
                    file=fddest,
                )
                print("  <->  sub * %s/%s/%s" % (fontname, se, sh), file=fddest)
                print("}{}", file=fddest)

            sh = "sl"
            if "it" in list(explodedFonts[family][se].keys()) and sh not in list(
                explodedFonts[family][se].keys()
            ):
                print(
                    (
                        "\\DeclareFontShape{%s}{%s}{%s}{%s}{"
                        % (encoding, fontname, "bx", sh)
                    ),
                    file=fddest,
                )
                print("  <->  sub * %s/%s/%s" % (fontname, se, "it"), file=fddest)
                print("}{}", file=fddest)

        # if there's sb but no b or bx, use sb in place of b and bx
        if (
            "sb" in list(explodedFonts[family].keys())
            and "b" not in list(explodedFonts[family].keys())
            and "bx" not in list(explodedFonts[family].keys())
        ):
            se = "sb"
            for bbx in ["b", "bx"]:
                for sh in explodedFonts[family][se]:
                    print(
                        (
                            "\\DeclareFontShape{%s}{%s}{%s}{%s}{"
                            % (encoding, fontname, bbx, sh)
                        ),
                        file=fddest,
                    )
                    print("  <->  sub * %s/%s/%s" % (fontname, se, sh), file=fddest)
                    print("}{}", file=fddest)

        print("\n\\endinput", file=fddest)
        fddest.close()

    for fontbase in list(styfiles.keys()):
        styoptions = styfiles[fontbase]
        print(styoptions)
        styname = niceFontName(fontbase)
        filename = filenameInLocaldir(styname + ".sty")
        stydest = open(filename, "w")
        print(
            (
                "%% Autogenerated by %s on %s"
                % (sys.argv[0], datetime.date.today().strftime("%Y/%m/%d"))
            ),
            file=stydest,
        )
        print(r"\NeedsTeXFormat{LaTeX2e}", file=stydest)
        print(
            (
                r"\ProvidesPackage{%s}[%s %s]"
                % (styname, datetime.date.today().strftime("%Y/%m/%d"), fontbase)
            ),
            file=stydest,
        )
        print(r"\RequirePackage[%s]{fontenc}" % encoding, file=stydest)
        print(r"\RequirePackage{textcomp}", file=stydest)
        print(r"\RequirePackage{xkeyval}", file=stydest)
        print(r"\RequirePackage{nfssext}", file=stydest)
        seensups = 0
        seensinf = 0
        for o in styoptions:
            if "sups" in o:
                seensups = 1
            if "sinf" in o:
                seensinf = 1
        if seensups:
            print(r"\def\@makefnmark{\hbox{\sustyle\@thefnmark}}", file=stydest)
            if seensinf:
                print(r"\providecommand*{\textfrac}[2]{%", file=stydest)
                print(r"  \textsu{#1}%", file=stydest)
                print(r"  \textfractionsolidus", file=stydest)
                print(r"  \textin{#2}}", file=stydest)
        str = r"\define@key{%s}{scaled}" % letterize(berryname[fontbase])
        if berryname[fontbase] in list(scaled.keys()):
            str += "[%s]" % scaled[berryname[fontbase]]
        else:
            str += "[1.0]"
        str += "{\def\%s@scaled{s*[#1]}}" % letterize(berryname[fontbase])
        print(str, file=stydest)
        str = r"\define@key{%s}{family}[rm]{\def\%s@family{#1}}" % (
            letterize(berryname[fontbase]),
            letterize(berryname[fontbase]),
        )
        print(str, file=stydest)
        print(r"\DeclareOption*{%", file=stydest)
        print(r"  \begingroup", file=stydest)
        print(r"  \edef\x{\endgroup", file=stydest)
        print(
            r"    \noexpand\setkeys{%s}{\CurrentOption}}%%"
            % letterize(berryname[fontbase]),
            file=stydest,
        )
        print(r"  \x}", file=stydest)

        onumprinted = False
        lnumprinted = False
        # change this if you don't want oldstyle to be the default
        oldstyleisdefault = True
        styledefaultprinted = False
        numoptions = ""
        for o in styoptions:
            if not onumprinted and "onum" in o:
                if oldstyleisdefault == True:
                    print(
                        (
                            r"\newcommand*{\%s@style}{%s}"
                            % (letterize(berryname[fontbase]), optionMappings["onum"])
                        ),
                        file=stydest,
                    )
                    styledefaultprinted = True
                numoptions += r"\DeclareOption{oldstyle}{%" + "\n"
                numoptions += r"  \renewcommand*{\%s@style}{%s}%%" % (
                    letterize(berryname[fontbase]),
                    optionMappings["onum"],
                )
                numoptions += "\n}\n"
                onumprinted = True
            if not lnumprinted and "lnum" in o:
                if oldstyleisdefault == False:
                    print(
                        (
                            r"\newcommand*{\%s@style}{%s}"
                            % (letterize(berryname[fontbase]), optionMappings["lnum"])
                        ),
                        file=stydest,
                    )
                    styledefaultprinted = True
                numoptions += r"\DeclareOption{lining}{%" + "\n"
                numoptions += r"  \renewcommand*{\%s@style}{%s}%%" % (
                    letterize(berryname[fontbase]),
                    optionMappings["lnum"],
                )
                numoptions += "\n}\n"
                lnumprinted = True
        if not lnumprinted and not onumprinted:
            print(
                (
                    r"\newcommand*{\%s@style}{%s}"
                    % (letterize(berryname[fontbase]), optionMappings["fakenum"])
                ),
                file=stydest,
            )
        print(numoptions, file=stydest)

        print(
            (r"\newcommand*{\%s@default}{%%" % letterize(berryname[fontbase])),
            file=stydest,
        )
        print(
            (
                r"  \renewcommand*{\rmdefault}{%s\%s@style}%%"
                % (berryname[fontbase], letterize(berryname[fontbase]))
            ),
            file=stydest,
        )
        print("}\n", file=stydest)

        for o in ["rm", "sf", "tt"]:
            print((r"\DeclareOption{%s}{%%" % o), file=stydest)
            print(
                (r"  \renewcommand*{\%s@default}{}%%" % letterize(berryname[fontbase])),
                file=stydest,
            )
            print(
                (
                    r"  \renewcommand*{\%sdefault}{%s\%s@style}%%"
                    % (o, berryname[fontbase], letterize(berryname[fontbase]))
                ),
                file=stydest,
            )
            print("}\n", file=stydest)

        print(r"\ProcessOptions*", file=stydest)
        print(r"\%s@default" % letterize(berryname[fontbase]), file=stydest)
        print(r"\endinput", file=stydest)
        stydest.close()


# given installcommands list, runs all commands in that list


def executeCommands():
    dryrun = False  # change to true to show commands but not run them
    if installcommands == []:
        sys.stderr.write(
            "Error: You don't seem to have specified any valid OTF fonts (or directories with OTF fonts in them).\n"
        )
        sys.exit()
    # call updmap manually at the end instead
    # installcommands[-1] = installcommands[-1].replace(" --no-updmap", "")
    for cmd in installcommands:
        print(cmd)
        if not dryrun:
            os.system(cmd)
    # typically these two need to be called at the end to clean up
    if not dryrun:
        # not thrilled to use "-user".
        # but by default, updmap.cfg is in /opt, and /opt should not
        # be writable. so -user it is.
        os.system("updmap -user")
        os.system("texhash")
        # os.system("updmap --syncwithtrees")
        os.system("updmap -user")


# break out all possibilities from a list
# breakout(['a', 'b'], ['c', '']) => [['a', 'c'], ['a'], ['b', 'c'], ['b']]
# Filters empty values out of output lists.
# breakout by Doug Zongker (thanks Doug!)


def breakout(lyst):
    if not lyst:
        yield []
    else:
        for i in lyst[0]:
            if i:
                for j in breakout(lyst[1:]):
                    yield [i] + j
            else:
                for j in breakout(lyst[1:]):
                    yield j


def filenameInLocaldir(str):
    p = subprocess.Popen(
        ["kpsewhich", "-expand-path=$TEXMFHOME"],
        universal_newlines=True,
        stdout=subprocess.PIPE,
    )
    output, _ = p.communicate()
    texmfhome = output.strip()
    print(texmfhome)
    return texmfhome + localfontsdir + str


removeproRE = re.compile(" pro")
removestdRE = re.compile(" std")


def niceFontName(str):
    return removestdRE.sub("", removeproRE.sub("", str.lower())).replace(" ", "")


# stable


def unique(s):
    u = {}
    ss = []
    for x in s:
        if x not in list(u.keys()):
            ss.append(x)
        u[x] = 1
    return ss


#######################################
# END UTILITY FUNCTIONS
#######################################

#######################################
# BEGIN GLOBAL VARIABLES
# DON'T TOUCH THESE
#######################################

# contains otftotfm commands to send to the os
installcommands = []

# indexed by font file name, contains (flat) info about font file:
# filename, family, subfamily, vendor, opticalSize, series, shape, features
fonthash = {}

# indexed by [family][series][shape], contains list of optical variants
# for each [family][series][shape]
classifiedFonts = {}

# indexed by [family][series][shape][optical], contains info for each optical
# variant:
# filename, vendor, fontname, cmdlineoptions
explodedFonts = {}

#######################################
# END GLOBAL VARIABLES
#######################################

#######################################
# BEGIN PROGRAM
#######################################

# checkOTFInfoVersion()
for font in generateFontfiles(sys.argv[1:]):
    addToFonthash(font)
populateFontDataStructures()
generateFDandSTY()
executeCommands()

#######################################
# END PROGRAM
#######################################
