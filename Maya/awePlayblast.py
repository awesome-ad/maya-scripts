"""This script playblasts the current scene and sends it through RVIO for viewing in RV.
Requires frameburn.mu
"""

import subprocess as sp
import maya.cmds as cmds
import maya.mel as mel
import re
import os
from tempfile import mkstemp
import time

pbViewVars = dict.fromkeys(['nurbsCurves', 'nurbsSurfaces', 'polymeshes',
                            'subdivSurfaces', 'planes', 'lights', 'cameras',
                            'joints', 'ikHandles', 'deformers', 'dynamics',
                            'fluids', 'hairSystems', 'follicles', 'nCloths',
                            'nParticles', 'nRigids', 'dynamicConstraints',
                            'locators', 'dimensions', 'pivots', 'handles',
                            'textures', 'strokes', 'motionTrails', 'pluginShapes',
                            'clipGhosts', 'greasePencils', 'cv', 'hulls',
                            'manipulators', 'grid', 'hud', 'sel', 'imagePlane',
                            'pluginObjects'
                            ], None)


def awePlayblast(scale=1, maxHeight=0, frameBurn=False, verbosity=1):
    """
    Playblasts for viewing in RV

    Keyword arguments:
    scale     : overall scaling factor (default 1)
    maxHeight : optional maximum height (default 0 = None)
    frameBurn : burn in frame values (default False)
    verbosity : output from encoding procedure (default 1)
                0 = no output, run in background
                1 = progress only
                2 = progress + shell output to script editor
                3 = progress + shell ouput + verbose encoder messages to script editor

    Description:
    Sets the viewport and camera up for optimal playblast settings, then
    playblasts the current timeSlider range to the project's /movies directory.
    Automatically detects previous Playblasts and names resulting movie file
    accordingly. Sends file to RVIO for conversion to H.264 and opens in RV.
    """

    # camera settings

    editor = cmds.playblast(ae=True)
    camera = cmds.modelEditor(editor, query=True, camera=True)

    storeEditorViewVars(editor)
    setupPlayblastView(editor)

    pze = cmds.camera(camera, q=True, pze=True)
    ovr = cmds.camera(camera, q=True, ovr=True)
    dr = cmds.camera(camera, q=True, dr=True)
    dfg = cmds.camera(camera, q=True, dfg=True)

    cmds.camera(camera, edit=True, pze=0, ovr=1.0, dfg=0, dr=0)

    # output folder detection
    # uses current project settings
    ws = cmds.workspace(q=True, rd=True)
    filerules = cmds.workspace(q=True, fr=True)
    movieDir = 'movies'
    if 'movies' in filerules:
        movieDir = filerules[filerules.index('movie') + 1]
    targetDir = ws + movieDir + "/"

    # make sure path exists
    if not os.path.exists(targetDir):
        os.mkdir(targetDir)

    # naming algorithm
    # filename based on scene name

    baseName = ""
    sceneName = cmds.file(q=True, sn=True, shn=True)
    if sceneName:
        baseName = os.path.splitext(sceneName)[0] + '_PB'
    else:
        baseName = 'untitled_PB'

    # file numbering

    existingPB = cmds.getFileList(fld=targetDir, fs=baseName + "*.mov")
    number = 1
    for pb in existingPB:
        n = re.search(r'_PB([0-9]+)', os.path.splitext(pb)[0]).group(1)
        if n:
            number = int(n) + 1
    version = str(number)
    if number < 10:
        version = "0" + version

    pbFileName = baseName + version
    pbExt = '.avi'
    pbFile = targetDir + pbFileName + pbExt

    # size algorithm
    # resolution is derived from render settings and
    # modified by scale and maxHeight arguments

    height = int(round(cmds.getAttr('defaultResolution.height') * scale))
    width = int(round(cmds.getAttr('defaultResolution.width') * scale))
    # adjust to max height if requested
    if maxHeight:
        if height > maxHeight:
            factor = float(maxHeight) / float(height)
            height = int(round(height * factor))
            width = int(round(width * factor))
    # make sure width is an even number or certain encoders will complain
    xWidth = width % 4
    xHeight = height % 4
    if xHeight or xWidth:
        # add or subtract to nearest number divisible by 4
        if xWidth <= 2:
            width -= xWidth
            height -= xHeight
        else:
            width += (4 - xWidth)
            height += (4 - xHeight)

    # playblast

    print "Playblasting at %(width)sx%(height)s to %(file)s\n" % \
          {'width': width, 'height': height, 'file': pbFile},

    pbResult = cmds.playblast(
        format="avi",
        forceOverwrite=True,
        filename=pbFile,
        sqt=False, cc=False, framePadding=0,
        viewer=False,
        showOrnaments=False,
        offScreen=True,
        percent=100, compression="none",
        quality=100, widthHeight=[width, height])

    restoreEditorViewVars(editor)

    rvFile = '"' + pbFile + '"'

    # playblast command only returns filename if it was not interrupted,
    # so we can check for user abort this way
    if pbResult:

        # run the batch file using subprocess,
        # pipe console output back into maya

        # create temporary .bat file
        tmpfileHandle, batFile = mkstemp(suffix='.bat')

        # build rvio command
        inputFile = pbFileName + pbExt
        outputFile = pbFileName + '.mov'

        rvioCmd = 'rvio_hw "%s" -codec libx264 -quality 1.0 -outparams vcc:profile=high vc:tune=animation vc:crf=18 ' % inputFile
        devNul = ''
        if not verbosity:
            devNul = ' >nul 2>&1'
        if verbosity == 1 or verbosity == 2:
            rvioCmd += '-v '
        if verbosity == 3:
            rvioCmd += '-vv '
        rvioCmd += '-o "%s"' % outputFile
        if frameBurn:
            offset = cmds.playbackOptions(query=True, min=True)
            rvioCmd += ' -overlay frameburnOffset 1.0 1.0 30 %s' % offset

        # build .bat file

        batCmd =  '@ECHO OFF\n'
        batCmd += '@cd /d "%s"\n' % targetDir
        batCmd += 'rvpush -tag playblast py-eval "pass"%s\n' % devNul
        batCmd += '%s\n' % rvioCmd
        batCmd += 'del "%s"%s\n' % (inputFile, devNul)
        batCmd += 'rvpush -tag playblast merge "%s" >nul 2>&1\n' % outputFile
        batCmd += 'rvpush -tag playblast py-exec \
                  "rv.commands.setViewNode(rv.commands.nodesOfType(\'RVSourceGroup\')[-1]); rv.commands.play()" >nul 2>&1'
        if not verbosity:
            batCmd += '\nstart /b "" cmd /c del "%~f0"&exit /b'

        # write to temp .bat file and close file handle
        os.write(tmpfileHandle, batCmd)
        os.close(tmpfileHandle)

        # run .bat and open a pipe to it
        if verbosity:

            # make sure to hide console window
            si = sp.STARTUPINFO()
            si.dwFlags |= sp.STARTF_USESHOWWINDOW
            si.wShowWindow = sp.SW_HIDE
            # execute
            pipe = sp.Popen(batFile,
                            stdout=sp.PIPE,
                            stderr=sp.STDOUT,
                            startupinfo=si,
                            cwd=targetDir)
            print "// RV: Encoding Playblast to x264 ...\n",

            gMainProgressBar = mel.eval("global string $gMainProgressBar; $blarf = $gMainProgressBar")
            cmds.progressBar(gMainProgressBar,
                             edit=True,
                             beginProgress=True,
                             isInterruptable=False,
                             status='Encoding Playblast to x264 ...',
                             maxValue=100)

            for line in iter(pipe.stdout.readline, ''):

                # progress bar
                # RVIO gives us progress info when using the -v flag
                if line.startswith("INFO: writing frame"):
                    matchPercent = re.search('\(([0-9.]+)%', line)
                    currentProgress = int(float(matchPercent.group(1)))
                    matchFrame = re.search(r'writing frame ([0-9]+)', line)
                    currentFrame = int(matchFrame.group(1))
                    cmds.progressBar(gMainProgressBar,
                                     edit=True,
                                     progress=currentProgress,
                                     status='Encoding to x264 (Frame %s)' % currentFrame)

                # standard output
                if verbosity > 1:
                    if not line.startswith("INFO [48]"):
                        print "// %s\n" % line.rstrip(),

            pipe.stdout.close()
            cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
            pipe.wait()

            print '// RV: Playblast complete: %s\n' % outputFile,

            # delete temporary .bat file
            os.remove(batFile)

        else:
            os.startfile(batFile)

    else:
        attempts = 0
        while attempts < 3:
            try:
                sp.check_output('DEL %s' % os.path.normpath(rvFile), shell=True)
            except sp.CalledProcessError as er:
                print er.cmd, er.output,
                time.sleep(1)
                attempts += 1
            else:
                break
        if attempts < 3:
            print '// Playblast aborted, file deleted.\n',
        else:
            print '// Playblast aborted, error deleting file.\n',

    # reset camera

    cmds.camera(camera, edit=True, pze=pze, ovr=ovr, dr=dr, dfg=dfg)

# store and retrieve modelEditor viewing options

def storeEditorViewVars(ed):

    if not cmds.optionVar(q='playblastOverrideViewport'):
        return

    global pbViewVars
    for key in pbViewVars.keys():
        if key == 'pluginObjects':
            piObjects = []
            pluginFilters = cmds.pluginDisplayFilter(q=True, listFilters=True)
            for fltr in pluginFilters:
                if not cmds.modelEditor(ed, q=True, queryPluginObjects=fltr):
                    piObjects.append(fltr)
            pbViewVars[key] = piObjects
        else:
            pbViewVars[key] = eval('cmds.modelEditor(ed, q=True, ' + key + '=True)')


def restoreEditorViewVars(ed):

    if not cmds.optionVar(q='playblastOverrideViewport'):
        return

    global pbViewVars
    for key, value in pbViewVars.items():
        if not key == 'pluginObjects':
            eval('cmds.modelEditor(ed, e=True, ' + key + '=' + str(value) + ')')
        else:
            pluginFilters = cmds.pluginDisplayFilter(q=True, listFilters=True)
            for fltr in pluginFilters:
                show = fltr in value
                cmds.modelEditor(ed, e=True, pluginObjects=[fltr, show])


def setupPlayblastView(ed):

    if not cmds.optionVar(q='playblastOverrideViewport'):
        return

    cmds.modelEditor(ed, e=True, nurbsCurves=cmds.optionVar(q='playblastShowNURBSCurves'))
    cmds.modelEditor(ed, e=True, nurbsSurfaces=cmds.optionVar(q='playblastShowNURBSSurfaces'))
    cmds.modelEditor(ed, e=True, polymeshes=cmds.optionVar(q='playblastShowPolyMeshes'))
    cmds.modelEditor(ed, e=True, subdivSurfaces=cmds.optionVar(q='playblastShowSubdivSurfaces'))
    cmds.modelEditor(ed, e=True, planes=cmds.optionVar(q='playblastShowPlanes'))
    cmds.modelEditor(ed, e=True, lights=cmds.optionVar(q='playblastShowLights'))
    cmds.modelEditor(ed, e=True, cameras=cmds.optionVar(q='playblastShowCameras'))
    cmds.modelEditor(ed, e=True, joints=cmds.optionVar(q='playblastShowJoints'))
    cmds.modelEditor(ed, e=True, ikHandles=cmds.optionVar(q='playblastShowIKHandles'))
    cmds.modelEditor(ed, e=True, deformers=cmds.optionVar(q='playblastShowDeformers'))
    cmds.modelEditor(ed, e=True, dynamics=cmds.optionVar(q='playblastShowDynamics'))
    cmds.modelEditor(ed, e=True, fluids=cmds.optionVar(q='playblastShowFluids'))
    cmds.modelEditor(ed, e=True, hairSystems=cmds.optionVar(q='query playblastShowHairSystems'))
    cmds.modelEditor(ed, e=True, follicles=cmds.optionVar(q='query playblastShowFollicles'))
    cmds.modelEditor(ed, e=True, nCloths=cmds.optionVar(q='playblastShowNCloths'))
    cmds.modelEditor(ed, e=True, nParticles=cmds.optionVar(q='playblastShowNParticles'))
    cmds.modelEditor(ed, e=True, nRigids=cmds.optionVar(q='playblastShowNRigids'))
    cmds.modelEditor(ed, e=True, dynamicConstraints=cmds.optionVar(q='playblastShowDynamicConstraints'))
    cmds.modelEditor(ed, e=True, locators=cmds.optionVar(q='playblastShowLocators'))
    cmds.modelEditor(ed, e=True, dimensions=cmds.optionVar(q='playblastShowDimensions'))
    cmds.modelEditor(ed, e=True, pivots=cmds.optionVar(q='playblastShowPivots'))
    cmds.modelEditor(ed, e=True, handles=cmds.optionVar(q='playblastShowHandles'))
    cmds.modelEditor(ed, e=True, textures=cmds.optionVar(q='playblastShowTextures'))
    cmds.modelEditor(ed, e=True, strokes=cmds.optionVar(q='playblastShowStrokes'))
    cmds.modelEditor(ed, e=True, motionTrails=cmds.optionVar(q='playblastShowMotionTrails'))
    cmds.modelEditor(ed, e=True, pluginShapes=cmds.optionVar(q='playblastShowPluginShapes'))
    cmds.modelEditor(ed, e=True, manipulators=cmds.optionVar(q='playblastShowManipulators'))
    cmds.modelEditor(ed, e=True, clipGhosts=cmds.optionVar(q='playblastShowClipGhosts'))
    cmds.modelEditor(ed, e=True, greasePencils=cmds.optionVar(q='playblastShowGreasePencils'))
    cmds.modelEditor(ed, e=True, cv=cmds.optionVar(q='playblastShowCVs'))
    cmds.modelEditor(ed, e=True, hulls=cmds.optionVar(q='playblastShowHulls'))
    cmds.modelEditor(ed, e=True, grid=cmds.optionVar(q='playblastShowGrid'))
    cmds.modelEditor(ed, e=True, hud=cmds.optionVar(q='playblastShowHUD'))
    cmds.modelEditor(ed, e=True, sel=cmds.optionVar(q='playblastShowSelectionHighlighting'))
    cmds.modelEditor(ed, e=True, imagePlane=cmds.optionVar(q='playblastShowImagePlane'))

    pluginFilters = cmds.pluginDisplayFilter(q=True, listFilters=True)
    playblastExclude = []
    if cmds.optionVar(exists='playblastShowPluginObjects'):
        playblastExclude.append(cmds.optionVar(q='playblastShowPluginObjects'))
    for fltr in pluginFilters:
        show = fltr in playblastExclude
        cmds.modelEditor(ed, e=True, pluginObjects=[fltr, show])
