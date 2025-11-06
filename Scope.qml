import QtQuick 2.15
import QtQuick.Window 2.2
import QtQuick.Layouts 1.15
import QtQuick.Shapes 1.15
import Friture 1.0
import "plotItemColors.js" as PlotItemColors

Plot {
    required property var viewModel
    required property string fixedFont

    scopedata: viewModel

    // Stage 1: double-click to create trigger (devPlan §1)
    onAreaDoubleClicked: function(xFrac, yFrac) {
        const level = viewModel.toLevel(yFrac);
        viewModel.add_trigger(level);
    }

    // Existing curve(s)
    Repeater {
        model: scopedata.plot_items
        PlotCurve {
            anchors.fill: parent
            color: PlotItemColors.color(index)
            curve: modelData
        }
    }

    // Stage 1: draw horizontal trigger lines
    Repeater {
        model: viewModel.triggers
        Rectangle {
            // depend on axis ticks so we recompute on range/scale changes
            readonly property var __tickDep: viewModel.vertical_axis.scale_division.logicalMajorTicks
            readonly property real frac: viewModel.toNormalizedY(modelData.trigger_level) + 0 * viewModel.axis_rev
            anchors.left: parent.left
            anchors.right: parent.right
            y: (1.0 - frac) * parent.height
            height: 1
            color: "#0B3D91" // dark blue
        }
    }

    TriggerParamsDialog {
        id: triggerParamsDialog
        viewModel: scopedata
    }

    // Stage 2: Right-click on trigger line opens the parameter dialog
    Repeater {
        model: viewModel.triggers
        Item {
            readonly property var __tickDep: viewModel.vertical_axis.scale_division.logicalMajorTicks
            readonly property real frac: viewModel.toNormalizedY(modelData.trigger_level) + 0 * viewModel.axis_rev

            anchors.left: parent.left
            anchors.right: parent.right
            y: (1.0 - frac) * parent.height - 4
            height: 9

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                height: 1
                color: "#0B3D91"
                opacity: 0.001
            }

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.RightButton
                onClicked: if (mouse.button === Qt.RightButton) {
                    triggerParamsDialog.openFor(modelData)
                }
            }
        }
    }
    
}