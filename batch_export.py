#! /usr/bin/env python

from concurrent.futures import ThreadPoolExecutor
import inkex
import os
import subprocess
import tempfile
import copy
import logging
import json
from lxml import etree
from inkex import BaseElement, Use, Layer, Group


# TODO Improve tests
def user_error(title, msg):
    logging.error(msg)
    user_message = "Error {}:\n{}".format(title, msg)
    inkex.errormsg(user_message)
    exit()


def is_clone(element):
    if element == None:
        return False
    ref_attrib_name = "{%s}href" % element.nsmap["xlink"]
    return ref_attrib_name in element.attrib


def get_name_element(element):
    if element == None:
        return ""
    return element.get("inkscape:label", "")


# Get hierarchy names (including self)
def get_element_hierarchy(element):
    return list(
        filter(
            None, map(get_name_element, reversed([element] + list(element.ancestors())))
        )
    )


class Options:
    def __init__(self, batch_exporter):
        self.current_file = batch_exporter.options.input_file

        # Export file page
        self.export_type = batch_exporter.options.export_type
        self.export_plain_svg = self._str_to_bool(
            batch_exporter.options.export_plain_svg
        )
        self.export_pdf_version = batch_exporter.options.export_pdf_version
        self.output_path = os.path.normpath(batch_exporter.options.path)
        self.overwrite_files = self._str_to_bool(batch_exporter.options.overwrite_files)
        self.export_manifest = self._str_to_bool(batch_exporter.options.export_manifest)

        # Controls page
        self.using_clones = self._str_to_bool(batch_exporter.options.using_clones)
        self.skip_hidden_layers = self._str_to_bool(
            batch_exporter.options.skip_hidden_layers
        )
        self.skip_prefix = batch_exporter.options.skip_prefix
        self.select_behavior = batch_exporter.options.select_behavior
        self.ignore_prefix = batch_exporter.options.ignore_prefix
        self.use_ignored_name = self._str_to_bool(
            batch_exporter.options.use_ignored_name
        )
        self.child_layers_visible = self._str_to_bool(
            batch_exporter.options.child_layers_visible
        )

        # Export size page
        self.export_area_type = batch_exporter.options.export_area_type
        self.export_area_size = batch_exporter.options.export_area_size
        self.export_res_type = batch_exporter.options.export_res_type
        self.export_res_dpi = batch_exporter.options.export_res_dpi
        self.export_res_width = batch_exporter.options.export_res_width
        self.export_res_height = batch_exporter.options.export_res_height

        # File naming page
        self.hierarchy_separator = batch_exporter.options.hierarchy_separator
        self.separator_strategy = batch_exporter.options.separator_strategy
        self.empty_extra_separator = self._str_to_bool(
            batch_exporter.options.empty_extra_separator
        )
        self.name_template = batch_exporter.options.name_template
        self.number_start = batch_exporter.options.number_start
        self.top_hierarchy_first = self._str_to_bool(
            batch_exporter.options.top_hierarchy_first
        )

        # Threads page
        self.number_threads = batch_exporter.options.number_threads
        self.chunks_size = batch_exporter.options.chunks_size

        # Help page
        self.use_logging = self._str_to_bool(batch_exporter.options.use_logging)
        if self.use_logging:
            self.log_path = os.path.expanduser(batch_exporter.options.log_path)
            self.overwrite_log = self._str_to_bool(batch_exporter.options.overwrite_log)
            log_file_name = os.path.join(self.log_path, "batch_export.log")
            if self.overwrite_log and os.path.exists(log_file_name):
                logging.basicConfig(
                    filename=log_file_name, filemode="w", level=logging.DEBUG
                )
            else:
                logging.basicConfig(filename=log_file_name, level=logging.DEBUG)

    def __str__(self):
        print = "\n===> EXTENSION PARAMETERS\n"
        print += "Current file: {}\n".format(self.current_file)
        print += "\n======> Export file page\n"
        print += "Export type: {}\n".format(self.export_type)
        print += "Export plain SVG: {}\n".format(self.export_plain_svg)
        print += "Export PDF version: {}\n".format(self.export_pdf_version)
        print += "Path: {}\n".format(self.output_path)
        print += "Overwrite files: {}\n".format(self.overwrite_files)
        print += "Export manifest JSON: {}\n".format(self.export_manifest)
        print += "\n======> Controls page\n"
        print += "Using clones: {}\n".format(self.using_clones)
        print += "Skip hidden layers: {}\n".format(self.skip_hidden_layers)
        print += "Skip prefix: {}\n".format(self.skip_prefix)
        print += "Select beahavior: {}\n".format(self.select_behavior)
        print += "Ignore prefix: {}\n".format(self.ignore_prefix)
        print += "Use ignored name (no prefix): {}\n".format(self.use_ignored_name)
        print += "Child layers always visible: {}\n".format(self.child_layers_visible)
        print += "\n======> Export size page\n"
        print += "Export area type: {}\n".format(self.export_area_type)
        print += "Export area size: {}\n".format(self.export_area_size)
        print += "Export res type: {}\n".format(self.export_res_type)
        print += "Export res DPI: {}\n".format(self.export_res_dpi)
        print += "Export res width: {}\n".format(self.export_res_width)
        print += "Export res height: {}\n".format(self.export_res_height)
        print += "\n======> File naming page\n"
        print += "Hierarchy separator: {}\n".format(self.hierarchy_separator)
        print += "Separator strategy: {}\n".format(self.separator_strategy)
        print += "Empty separator: {}\n".format(self.empty_extra_separator)
        print += "Name template: {}\n".format(self.name_template)
        print += "Start count at: {}\n".format(self.number_start)
        print += "\n======> Threads page\n"
        print += "Number threads: {}\n".format(self.number_threads)
        print += "Chunks size: {}\n".format(self.chunks_size)
        print += "\n======> Help page\n"
        print += "Use logging: {}\n".format(self.use_logging)
        print += "Overwrite log: {}\n".format(self.overwrite_log)
        print += "Log path: {}\n".format(self.log_path)
        print += "---------------------------------------\n"
        return print

    def _str_to_bool(self, str):
        if str.lower() == "true":
            return True
        return False


class BatchExporter(inkex.EffectExtension):
    def __init__(self):
        """init the effetc library and get options from gui"""
        inkex.Effect.__init__(self)

        # Export file page
        self.arg_parser.add_argument(
            "--export-type",
            action="store",
            type=str,
            dest="export_type",
            default="svg",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-plain-svg",
            action="store",
            type=str,
            dest="export_plain_svg",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--export-pdf-version",
            action="store",
            type=str,
            dest="export_pdf_version",
            default="1.5",
            help="",
        )
        self.arg_parser.add_argument(
            "--path",
            action="store",
            type=str,
            dest="path",
            default="",
            help="export path",
        )
        self.arg_parser.add_argument(
            "--overwrite-files",
            action="store",
            type=str,
            dest="overwrite_files",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--export-manifest",
            action="store",
            type=str,
            dest="export_manifest",
            default=True,
            help="",
        )

        # Controls page
        self.arg_parser.add_argument(
            "--using-clones",
            action="store",
            type=str,
            dest="using_clones",
            default=True,
            help="",
        )
        self.arg_parser.add_argument(
            "--skip-hidden-layers",
            action="store",
            type=str,
            dest="skip_hidden_layers",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--skip-prefix",
            action="store",
            type=str,
            dest="skip_prefix",
            default="_",
            help="",
        )
        self.arg_parser.add_argument(
            "--select-behavior",
            action="store",
            type=str,
            dest="select_behavior",
            default="only-leaf",
            help="",
        )
        self.arg_parser.add_argument(
            "--ignore-prefix",
            action="store",
            type=str,
            dest="ignore_prefix",
            default="_",
            help="",
        )
        self.arg_parser.add_argument(
            "--use-ignored-name",
            action="store",
            type=str,
            dest="use_ignored_name",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--child-layers-visible",
            action="store",
            type=str,
            dest="child_layers_visible",
            default=True,
            help="",
        )

        # Export size page
        self.arg_parser.add_argument(
            "--export-area-type",
            action="store",
            type=str,
            dest="export_area_type",
            default="page",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-area-size",
            action="store",
            type=str,
            dest="export_area_size",
            default="0:0:100:100",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-res-type",
            action="store",
            type=str,
            dest="export_res_type",
            default="default",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-res-dpi",
            action="store",
            type=int,
            dest="export_res_dpi",
            default="96",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-res-width",
            action="store",
            type=int,
            dest="export_res_width",
            default="100",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-res-height",
            action="store",
            type=int,
            dest="export_res_height",
            default="100",
            help="",
        )

        # File naming page
        self.arg_parser.add_argument(
            "--name-template",
            action="store",
            type=str,
            dest="name_template",
            default="[LAYER_NAME]",
            help="",
        )
        self.arg_parser.add_argument(
            "--number-start",
            action="store",
            type=int,
            dest="number_start",
            default="0",
            help="",
        )
        self.arg_parser.add_argument(
            "--hierarchy-separator",
            action="store",
            type=str,
            dest="hierarchy_separator",
            default="_",
            help="",
        )
        self.arg_parser.add_argument(
            "--separator-strategy",
            action="store",
            type=str,
            dest="separator_strategy",
            default="both",
            help="",
        )
        self.arg_parser.add_argument(
            "--empty-extra-separator",
            action="store",
            type=str,
            dest="empty_extra_separator",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--top-hierarchy-first",
            action="store",
            type=str,
            dest="top_hierarchy_first",
            default=False,
            help="",
        )

        # Theads page
        self.arg_parser.add_argument(
            "--number-threads",
            action="store",
            type=int,
            dest="number_threads",
            default="4",
            help="",
        )
        self.arg_parser.add_argument(
            "--chunks-size",
            action="store",
            type=int,
            dest="chunks_size",
            default="1",
            help="",
        )

        # Help page
        self.arg_parser.add_argument(
            "--use-logging",
            action="store",
            type=str,
            dest="use_logging",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--overwrite-log",
            action="store",
            type=str,
            dest="overwrite_log",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--log-path", action="store", type=str, dest="log_path", default="", help=""
        )

        # HACK - the script is called with a "--tab controls" option as an argument from the notebook param in the inx file.
        # This argument is not used in the script. It's purpose is to suppress an error when the script is called.
        self.arg_parser.add_argument(
            "--tab", action="store", type=str, dest="tab", default="controls", help=""
        )

    def _debug_svg_doc_wait(self, doc):
        # Can't use delete=True, delete_on_close=False, since Inkscape use python 2.7
        with tempfile.NamedTemporaryFile(delete=False, suffix=".svg") as temporary_file:
            doc.write(temporary_file.name)
            temporary_file.close()

            logging.debug("    Debug temp file {}".format(temporary_file.name))

            with subprocess.Popen(
                ["start", "/WAIT", temporary_file.name], shell=True
            ) as proc:
                proc.wait()

            os.remove(temporary_file.name)

    def effect(self):
        # Check user options
        options = Options(self)
        logging.debug(options)

        # Is working on self.document is safe ? Security
        self.working_doc = copy.deepcopy(self.document)

        # Build the partial inkscape export command
        command = self.build_partial_command(options)

        # Replace or delete clones
        self.handles_clones(options.using_clones)

        # Delete skip branches
        self.delete_skipped_layers(options.skip_hidden_layers, options.skip_prefix)

        # Get the layers selected
        layers_infos = self.get_layers(options.select_behavior, options.ignore_prefix)

        # Construct and path (duplicate names, file exists)
        layers_export = self.fill_and_check_paths(layers_infos, options)

        doc = self.create_base_export_document()

        logging.debug(
            "\n---------------------------------------\n===> EXPORT PARALLEL\n---------------------------------------\n"
        )
        files_result = []
        with ThreadPoolExecutor(max_workers=options.number_threads) as executor:
            files_result = list(
                executor.map(
                    self.construct_thread(
                        doc, command, options.use_logging, options.child_layers_visible
                    ),
                    layers_export.items(),
                    chunksize=options.chunks_size,
                )
            )

        # for result in files_result:
        #     logging.debug(result)

        if options.export_manifest:
            logging.debug(
                "\n---------------------------------------\n===> JSON\n---------------------------------------\n"
            )
            # Json manifest
            self.export_manifest(layers_export, options.output_path)

    def handles_clones(self, using_clones):
        svg_clones = self.working_doc.xpath(
            "//svg:use[@xlink:href]", namespaces=inkex.NSS
        )

        # Depth first
        for clone in reversed(svg_clones):
            if using_clones:
                copy = clone.unlink()
                while is_clone(copy):
                    copy = copy.unlink()

                # Special case style
                if float(clone.style.get("opacity", 1)) <= 0.0:
                    copy.style["opacity"] = 0
                    copy.style.update(copy.style)

                # Change layer to group when unlinking
                for child in copy.iter():
                    if Layer.is_class_element(child):
                        child.set("inkscape:groupmode", "")
            else:
                clone.delete()

        # self._debug_svg_doc_wait(self.working_doc)

    def delete_skipped_layers(self, skip_hidden_layers, skip_prefix):
        doc = self.working_doc

        svg_layers = doc.xpath(
            '//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS
        )

        nb_skipped = 0
        for layer in svg_layers:
            layer_label = get_name_element(layer)

            # Delete skip_prefix or hidden layers
            if layer_label.startswith(skip_prefix) or (
                skip_hidden_layers
                and "style" in layer.attrib
                and "display:none" in layer.attrib["style"]
            ):
                logging.debug("  Skip: [{}]".format(layer_label))
                layer.delete()
                nb_skipped += 1

        logging.debug("  TOTAL NUMBER OF LAYERS SKIPPED: {}\n".format(nb_skipped))
        # self._debug_svg_doc_wait(doc)

    def get_layers(self, select_behavior, ignore_prefix):
        doc = self.working_doc
        svg_layers = doc.xpath(
            '//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS
        )

        layers_infos = []

        for layer in svg_layers:
            layer_label = get_name_element(layer)
            if layer_label == "":
                continue

            if layer_label.startswith(ignore_prefix):
                logging.debug("  Ignored (prefix): [{}]".format(layer_label))
                continue

            # Check if parent
            is_parent = any(
                Layer.is_class_element(child)
                and not get_name_element(child).startswith(ignore_prefix)
                for child in layer.getchildren()
            )

            if select_behavior == "only-leaf" and is_parent:
                logging.debug(
                    "  Not selected (use only leafs): [{}]".format(layer_label)
                )
                continue

            # Get layer hierarchy (including self)
            hierarchy = get_element_hierarchy(layer)

            layer_info = (layer, hierarchy)
            layers_infos.append(layer_info)

        logging.debug("  TOTAL NUMBER OF LAYERS: {}\n".format(len(layers_infos)))

        # self._debug_svg_doc_wait(doc)
        return layers_infos

    def fill_and_check_paths(self, layer_infos, options: Options):
        counter = options.number_start

        layers_export = {}

        for layer, hierarchy in layer_infos:
            path = self.get_path(hierarchy, counter, options)

            # Check if layer have same name or path (with ignored layers)
            if not path in layers_export:
                layers_export[path] = (layer, hierarchy, counter)
            else:
                layer_path = (">").join(hierarchy)
                layer_path_existing = (">").join(layers_export[path][1])
                user_error(
                    "Same layer name",
                    "Some layers have the same name, and the same path:\n"
                    "{}\n{}\nPath ->{}\nPlease change names on layers.\n".format(
                        layer_path, layer_path_existing, path
                    ),
                )
                return {}

            # Check if the file exists. If not, export it.
            if not options.overwrite_files and os.path.exists(path):
                user_error(
                    "File already exists",
                    f"File {path} already exist, check overwrite files if it's not an error.",
                )
                return {}

            counter += 1

        return layers_export

    def get_path(self, hierarchy, counter, options: Options):
        path = options.name_template

        # Ignore self for hierarchy keyword
        layers_name = hierarchy[-1]
        layers_hierarchy: list = hierarchy[:-1]

        if not options.top_hierarchy_first:
            layers_hierarchy = list(reversed(layers_hierarchy))

        # Extra separators conditions
        add_left_sep = (layers_hierarchy != [] or options.empty_extra_separator) and (
            options.separator_strategy == "left" or options.separator_strategy == "both"
        )
        add_right_sep = (layers_hierarchy != [] or options.empty_extra_separator) and (
            options.separator_strategy == "right"
            or options.separator_strategy == "both"
        )
        # logging.debug(
        #     "  Extra separators: [left={}, right={}]".format(
        #         add_left_sep, add_right_sep
        #     )
        # )

        # Add an extra element to add extra separators if empty (but not if both, redundant, or none)
        if (
            options.empty_extra_separator
            and layers_hierarchy == []
            and options.separator_strategy != "both"
            and options.separator_strategy != "none"
        ):
            layers_hierarchy = [""]
        if add_left_sep:
            layers_hierarchy = [""] + layers_hierarchy
        if add_right_sep:
            layers_hierarchy = layers_hierarchy + [""]

        # Replace
        path = path.replace(
            "[HIERARCHY]",
            (options.hierarchy_separator).join(
                [
                    parent_name.removeprefix(options.ignore_prefix)
                    for parent_name in layers_hierarchy
                    if options.use_ignored_name
                    or not parent_name.startswith(options.ignore_prefix)
                ]
            ),
        )

        path = path.replace("[LAYER_NAME]", layers_name)
        path = path.replace("[NUM]", str(counter))
        path = path.replace("[NUM-1]", str(counter).zfill(1))
        path = path.replace("[NUM-2]", str(counter).zfill(2))
        path = path.replace("[NUM-3]", str(counter).zfill(3))
        path = path.replace("[NUM-4]", str(counter).zfill(4))
        path = path.replace("[NUM-5]", str(counter).zfill(5))
        path = "{}.{}".format(path, options.export_type)
        # Special case user separator break local path
        path = path.removeprefix("/").removeprefix("\\")
        destination_path = os.path.join(options.output_path, path)
        destination_path = os.path.normpath(destination_path)
        return destination_path

    def create_base_export_document(self):
        doc = copy.deepcopy(self.working_doc)

        to_delete = []

        # Remove all elements with a name (make a white document with options)
        for element in doc.getroot().getchildren():
            element_label = get_name_element(element)
            if element_label == "":
                continue
            element.delete()

        return doc

    def build_partial_command(self, options):
        command = ["inkscape", "--vacuum-defs"]

        if options.export_type == "svg" and options.export_plain_svg == True:
            command.append("--export-plain-svg")
        if options.export_type == "pdf":
            command.append("--export-pdf-version={}".format(options.export_pdf_version))

        # Export area - default: export area page
        if options.export_area_type == "drawing":
            command.append("--export-area-drawing")
        elif options.export_area_type == "custom":
            command.append("--export-area={}".format(options.export_area_size))
        else:
            command.append("--export-area-page")

        # Export res - default: no arguments
        if options.export_res_type == "dpi":
            command.append("--export-dpi={}".format(options.export_res_dpi))
        elif options.export_res_type == "size":
            command.append("--export-width={}".format(options.export_res_width))
            command.append("--export-height={}".format(options.export_res_height))

        return command

    def construct_thread(self, doc, base_command, use_logging, child_visible):
        def export_layer_threaded(layer_export):
            export_doc = copy.deepcopy(doc)

            path, (layer, _, _) = layer_export
            copy_layer = copy.deepcopy(layer)

            # Add the layer inside fresh document
            root = export_doc.getroot()

            # Handle transform hierarchy
            container = Layer.new("root")
            parent = layer.getparent()
            if parent != None:
                container.transform = parent.composed_transform()
            root.append(container)

            copy_layer.attrib["style"] = "display:inline"
            container.append(copy_layer)

            svg_layers = export_doc.xpath(
                '//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS
            )

            if child_visible:
                for element in svg_layers:
                    if "style" not in element.attrib:
                        continue
                    element.attrib["style"] = "display:inline"

            # self._debug_svg_doc_wait(export_doc)

            # Save the data in a temporary file
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".svg"
            ) as temporary_file:

                export_doc.write(temporary_file.name)
                temporary_file.close()

                self.export_to_file(
                    base_command.copy(),
                    temporary_file.name,
                    path,
                    use_logging,
                )

            os.remove(temporary_file.name)
            return True

        return export_layer_threaded

    def export_to_file(self, command, svg_path, output_path, use_logging):
        command.append("--export-filename=%s" % output_path)
        command.append(svg_path)
        logging.debug("  {}\n{}\n".format(output_path, command))

        # Create the output folder if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            if use_logging:
                # If not piped, stdout and stderr will be showed in an inkscape dialog at the end.
                # Inkscape export will create A LOT of warnings, most of them repeated, and I believe
                # it is pointless to crowd the log file with these warnings.
                with subprocess.Popen(command) as proc:
                    proc.wait(timeout=300)
            else:
                with subprocess.Popen(
                    command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                ) as proc:
                    proc.wait(timeout=300)
        except OSError:
            user_error(
                "OS Error exporting", "Error while exporting file {}.".format(command)
            )

    def export_manifest(self, layer_exports, output_path):
        json_root = []
        for path, (_, hierarchy, counter) in layer_exports.items():
            json_element, all_children = self.create_json_elements(json_root, hierarchy)
            json_root = all_children

            json_element["path"] = path
            json_element["order"] = counter

        manifest_path = os.path.join(output_path, "manifest.json")
        logging.debug("  Export manifest to {}\n".format(manifest_path))
        with open(manifest_path, "w+", encoding="utf-8") as f:
            json.dump(json_root, f, ensure_ascii=False, indent=4)

    def create_json_elements(self, parent_children, hierarchy, parent=None):
        if hierarchy == []:
            return (parent, parent_children)

        element_name = hierarchy[0]
        ancestors = hierarchy[1:]

        json_element = next(
            (el for el in parent_children if el["name"] == element_name), None
        )

        if json_element == None:
            json_element = {"name": element_name, "children": []}
            parent_children.append(json_element)

        (leaf, children) = self.create_json_elements(
            json_element["children"], ancestors, json_element
        )
        json_element["children"] = children

        return (leaf, parent_children)


def _main():
    exporter = BatchExporter()
    exporter.run()
    exit()


if __name__ == "__main__":
    _main()
