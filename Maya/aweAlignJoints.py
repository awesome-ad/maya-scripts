"""
aweAlignJoints.py
Author: AwesomeAD

Align three selected joints to the implicit plane on which they lie.

While the Orient Joint tool (joint command) allows us to orient a secondary axis to a
normal of the plane of its parent and child by omitting the secondary axis, it is not
possible to choose which of two normals, nor does it guarantee clean orientations.
This tool rectifies that by allowing the choice of normal and ensuring that the
middle joint (in a hierarchy) will have an orientation in the secondary axis only.

Usage in Maya:
import aweAlignJoints
aweAlignJoints.align()
"""


from PySide2 import QtCore, QtWidgets
from shiboken2 import wrapInstance
from maya.OpenMayaUI import MQtUtil
import maya.api.OpenMaya as om
import maya.cmds as cmds
import math


def buildMatrix(aimVector, normalVector, primary, secondary):
    """ Build a Matrix with the the given vectors in the given rows.

        i.e. the `aimVector` should land in the row given by the `primary` axis,
        the `normalVector` should land in the row given by the `secondary` axis
        0 = X, 1 = Y, 2 = Z
    """

    order = [primary, secondary]
    # find remaining (tertiary) axis
    order.append(3 - sum(order))
    aimRow = [aimVector.x, aimVector.y, aimVector.z, 0]
    normalRow = [normalVector.x, normalVector.y, normalVector.z, 0]
    thirdVector = aimVector ^ normalVector
    thirdRow = [thirdVector.x, thirdVector.y, thirdVector.z, 0]
    tRow = [0, 0, 0, 1]
    rows = [aimRow, normalRow, thirdRow]
    rowList = [[], [], [], []]
    for i, axis in enumerate(order):
        rowList[axis] = rows[i]
    # flatten list
    mList = [a for row in rowList for a in row]
    mList.extend(tRow)
    mtx = om.MMatrix(mList)
    # a left-handed matrix will cause the aim axis to be reflected when decomposed;
    # multiplying with a negative determinant flips the third axis to rectify this
    det = mtx.det3x3()
    for i in range(3):
        mtx.setElement(order[2], i, thirdRow[i] * det)
    return mtx


def planeJoints(root, mid, end, primaryAxis, secondaryAxis, reflect=False):
    """ Orient 3 joints to the plane they form.

        `primaryAxis`: axis to point at the next joint (0=X, 1=Y, 2=Z)
        `secondaryAxis`: axis to align orthogonal to the plane.
        `reflect`: flips the `secondaryAxis` if desired
    """

    rootPos = om.MVector(cmds.xform(root, q=True, ws=True, t=True))
    midPos = om.MVector(cmds.xform(mid, q=True, ws=True, t=True))
    endPos = om.MVector(cmds.xform(end, q=True, ws=True, t=True))
    endMtx = om.MMatrix(cmds.getAttr(end + ".worldMatrix"))
    
    root2mid = midPos - rootPos
    mid2end = endPos - midPos
    root2end = endPos - rootPos
    normal = root2end ^ root2mid
    if reflect:
        normal *= -1
    
    # reset rotations to 0, create appropriate object space rotation matrix, apply rotation to jointOrient
    cmds.xform(root, os=True, ro=[0, 0, 0])
    rootMtx = buildMatrix(root2mid.normalize(), normal.normalize(), primaryAxis, secondaryAxis)
    # transform rootMtx into object space
    rootParentMtx = om.MMatrix(cmds.getAttr(root + ".pim"))
    rootMtx *= rootParentMtx
    rootRot = om.MTransformationMatrix(rootMtx).rotation()
    cmds.setAttr(root + ".jo", math.degrees(rootRot.x), math.degrees(rootRot.y), math.degrees(rootRot.z), type="double3")
    
    # mid joint has probably moved; reset its position, then repeat the above steps for it
    cmds.xform(mid, ws=True, t=[midPos.x, midPos.y, midPos.z])
    cmds.xform(mid, os=True, ro=[0, 0, 0])
    midMtx = buildMatrix(mid2end.normalize(), normal.normalize(), primaryAxis, secondaryAxis)
    midParentMtx = om.MMatrix(cmds.getAttr(mid + ".pim"))
    midMtx *= midParentMtx
    midRot = om.MTransformationMatrix(midMtx).rotation()
    # if the computed rotation is such that it requires rotation around all 3 axes,
    # use the alternate solution. Only relevant if mid is a direct child of root (and
    # hence a rotation around its secondary axis would suffice)
    if all(map(lambda x: abs(x) >= 1e-08, midRot)):
        midRot = midRot.alternateSolution()
    cmds.setAttr(mid + ".jo", math.degrees(midRot.x), math.degrees(midRot.y), math.degrees(midRot.z), type="double3")
    
    # reset third joint to its original world space position and orientation
    cmds.xform(end, ws=True, t=[endPos.x, endPos.y, endPos.z])
    cmds.xform(end, os=True, ro=[0, 0, 0])
    endParentMtx = om.MMatrix(cmds.getAttr(end + ".pim"))
    endMtx *= endParentMtx
    endRot = om.MTransformationMatrix(endMtx).rotation()
    cmds.setAttr(end + ".jo", math.degrees(endRot.x), math.degrees(endRot.y), math.degrees(endRot.z), type="double3")


def main_window():
    window_ptr = MQtUtil.mainWindow()
    return wrapInstance(long(window_ptr), QtWidgets.QWidget)


class aweAlignWidget(QtWidgets.QDialog):
    """ The UI for this tool. """

    # singleton instance
    instance = None
    
    def __init__(self, parent=main_window()):
        super(aweAlignWidget, self).__init__(parent)
        self.setWindowTitle("aweAlignJoints")
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setSizeGripEnabled(False)
        self.createLayout()
        self.destroyed.connect(self.__class__.resetInstance)
        
    def createLayout(self):
        mainLayout = QtWidgets.QVBoxLayout(self)
        mainLayout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        
        axisLayout = QtWidgets.QHBoxLayout()
        mainLayout.addLayout(axisLayout)
        
        primaryLayout = QtWidgets.QVBoxLayout()
        axisLayout.addLayout(primaryLayout)
        pLabel = QtWidgets.QLabel("Aim Axis")
        primaryLayout.addWidget(pLabel)
        primaryButtonsLayout = QtWidgets.QHBoxLayout()
        primaryLayout.addLayout(primaryButtonsLayout)
        self.pGroup = QtWidgets.QButtonGroup(self)
        self.pX = QtWidgets.QRadioButton("X")
        self.pY = QtWidgets.QRadioButton("Y")
        self.pZ = QtWidgets.QRadioButton("Z")
        self.pGroup.addButton(self.pX, 0)
        self.pGroup.addButton(self.pY, 1)
        self.pGroup.addButton(self.pZ, 2)
        self.pGroup.buttonToggled.connect(self.pAxisToggled)
        primaryButtonsLayout.addWidget(self.pX)
        primaryButtonsLayout.addWidget(self.pY)
        primaryButtonsLayout.addWidget(self.pZ)
        primaryLayout.addStretch(1)
        
        secondaryLayout = QtWidgets.QVBoxLayout()
        axisLayout.addLayout(secondaryLayout)
        sLabel = QtWidgets.QLabel("Up Axis")
        secondaryLayout.addWidget(sLabel)
        secondaryButtonsLayout = QtWidgets.QHBoxLayout()
        secondaryLayout.addLayout(secondaryButtonsLayout)
        self.sGroup = QtWidgets.QButtonGroup(self)
        self.sX = QtWidgets.QRadioButton("X")
        self.sY = QtWidgets.QRadioButton("Y")
        self.sZ = QtWidgets.QRadioButton("Z")
        self.sGroup.addButton(self.sX, 0)
        self.sGroup.addButton(self.sY, 1)
        self.sGroup.addButton(self.sZ, 2)
        secondaryButtonsLayout.addWidget(self.sX)
        secondaryButtonsLayout.addWidget(self.sY)
        secondaryButtonsLayout.addWidget(self.sZ)
        secondaryLayout.addSpacing(10)
        self.reverseBtn = QtWidgets.QCheckBox("Reverse")
        secondaryLayout.addWidget(self.reverseBtn)
        self.pX.setChecked(True)
        self.sY.setChecked(True)
                                
        axisLayout.insertSpacing(1, 18)
        axisLayout.addStretch(1)
        mainLayout.addSpacing(10)
        mainLayout.addStretch(1)
        
        buttonLayout = QtWidgets.QHBoxLayout()
        mainLayout.addLayout(buttonLayout)
        okBtn = QtWidgets.QPushButton("Align")
        okBtn.setDefault(True)
        okBtn.clicked.connect(self.doAlign)
        cancelBtn = QtWidgets.QPushButton("Cancel")
        cancelBtn.clicked.connect(self.close)
        buttonLayout.addWidget(okBtn)
        buttonLayout.addWidget(cancelBtn)
        buttonLayout.insertStretch(0, 1)
        
    def pAxisToggled(self, btn, state):
        grp = self.sender()
        id = grp.id(btn)
        if state is True:
            self.sGroup.button(id).setEnabled(False)
            if self.sGroup.checkedId() == id:
                self.sGroup.button(id).setChecked(False)
                nextId = (id + 1) % 3
                self.sGroup.button(nextId).setChecked(True)
        else:
            self.sGroup.button(id).setEnabled(True)

    def doAlign(self):
        pAxis = self.pGroup.checkedId()
        sAxis = self.sGroup.checkedId()
        reflect = self.reverseBtn.isChecked()
        sel = cmds.ls(sl=True, l=True, tr=True)
        if len(sel) == 3:
            root, mid, end = sel
            planeJoints(root, mid, end, pAxis, sAxis, reflect)
        else:
            cmds.warning("Please select 3 joints")

    @classmethod
    def resetInstance(cls):
        """ Reset this singleton value
        If this isn't a class- or staticmethod, the QObject.destroyed() signal can't see it
        """
        cls.instance = None


def align():
    if aweAlignWidget.instance is None:
        aweAlignWidget.instance = aweAlignWidget()
    aweAlignWidget.instance.show()
    aweAlignWidget.instance.activateWindow()
