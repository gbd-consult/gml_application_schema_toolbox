import os

from PyQt4 import QtGui
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from lxml import etree

from complex_features import noPrefix

import urllib

def fill_tree_with_element(widget, treeItem, elt):
    # tag
    if elt.prefix:
        treeItem.setText(0, elt.prefix + ':' + noPrefix(elt.tag))
    else:
        treeItem.setText(0, noPrefix(elt.tag))
    f = treeItem.font(0)
    f.setBold(True)
    treeItem.setFont(0,f)

    # attributes
    for k, v in elt.attrib.iteritems():
        child = QTreeWidgetItem()
        treeItem.addChild(child)
        if '}' in k:
            i = k.index('}')
            ns = k[1:i]
            # get ns prefix from ns uri
            n = elt.nsmap.keys()[elt.nsmap.values().index(ns)] + ":" + k[i+1:]
        else:
            n = noPrefix(k)
        child.setText(0, "@" + n)
        if n == 'xlink:href' and v.startswith('http'):
            html = QLabel(widget)
            html.setOpenExternalLinks(True)
            html.setTextFormat(Qt.RichText)
            html.setText('<a href="{}">{}</a>'.format(v, v))
            #child.setText(1, '<a href="{}">{}</a>'.format(v, v))
            child.setData(1, Qt.UserRole, v)
            widget.setItemWidget(child, 1, html)
        else:
            child.setText(1, v)
    # text
    if elt.text:
        treeItem.setText(1, elt.text)
        
    # children
    for xmlChild in elt:
        if isinstance(xmlChild, etree._Comment):
            continue
        child = QTreeWidgetItem()
        treeItem.addChild(child)
        fill_tree_with_element(widget, child, xmlChild)

def recurse_expand(treeItem):
    treeItem.setExpanded(True)
    for i in range(treeItem.childCount()):
        recurse_expand(treeItem.child(i))

def fill_tree_with_xml(treeWidget, xml):
    """
    Fill a QTreeWidget with XML nodes.
    :param treeWidget: a QTreeWidget
    :param xml: the XML content, as string
    """
    tree = etree.XML(xml)
    treeWidget.clear()
    treeWidget.setColumnCount(2)
    fill_tree_with_element(treeWidget, treeWidget.invisibleRootItem(), tree)
    recurse_expand(treeWidget.invisibleRootItem())
    treeWidget.resizeColumnToContents(0)
    treeWidget.resizeColumnToContents(1)

class XMLTreeWidget(QtGui.QTreeWidget):
    def __init__(self, parent = None):
        """Constructor.
        :param feature: a QgsFeature
        :param parent: a QWidget parent
        """
        super(XMLTreeWidget, self).__init__(parent)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setWordWrap(True)
        self.setExpandsOnDoubleClick(False)
        self.headerItem().setText(0, "Element")
        self.headerItem().setText(1, "Value")
        self.header().setVisible(True)
        self.header().setCascadingSectionResizes(True)

        self.customContextMenuRequested.connect(self.onContextMenu)

    def updateFeature(self, feature):
        x = None
        try:
            x = feature.attribute('_xml_')
        except KeyError:
            pass
        if x:
            fill_tree_with_xml(self, x)

    def onContextMenu(self, pos):
        row = self.selectionModel().selectedRows()[0]
        menu = QMenu(self)
        copyAction = QAction(u"Copy value", self)
        copyAction.triggered.connect(self.onCopyItemValue)
        copyXPathAction = QAction(u"Copy XPath", self)
        copyXPathAction.triggered.connect(self.onCopyXPath)
        resolveAction = QAction(u"Resolve external", self)
        resolveAction.triggered.connect(self.onResolveExternal)
        menu.addAction(copyAction)
        menu.addAction(copyXPathAction)

        item = self.currentItem()
        if item.text(0) == '@xlink:href' and item.data(1, Qt.UserRole).startswith('http'):
            menu.addAction(resolveAction)

        menu.popup(self.mapToGlobal(pos))

    def onCopyXPath(self):
        def get_xpath(item):
            s = ''
            if item.parent():
                s = get_xpath(item.parent())
            return s + "/" + item.text(0)

        xpath = get_xpath(self.currentItem())
        QApplication.clipboard().setText(xpath)

    def onCopyItemValue(self):
        QApplication.clipboard().setText(self.currentItem().text(1))

    def onResolveExternal(self):
        item = self.currentItem()
        if item.text(0) == '@xlink:href' and item.data(1, Qt.UserRole).startswith('http'):
            QApplication.setOverrideCursor(Qt.WaitCursor)
            uri = item.data(1, Qt.UserRole)
            try:
                f = urllib.urlopen(uri)
                try:
                    xml = etree.parse(f)
                except etree.XMLSyntaxError:
                    # probably not an XML
                    QApplication.restoreOverrideCursor()
                    QMessageBox.warning(self, "XML parsing error", "The external resource is not a well formed XML")
                    return

                fill_tree_with_element(self, item.parent(), xml.getroot())
            finally:
                QApplication.restoreOverrideCursor()
